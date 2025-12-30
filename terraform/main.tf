variable "ocr_api_key" {
  description = "The API key for OCR.space"
  type        = string
  sensitive   = true
}

variable "alert_email" {
  description = "Email address for high-risk alerts"
  type        = string
  sensitive   = true
}

provider "aws" {
  region = "ap-south-1"  # Mumbai Region
}

# --- 1. S3 BUCKET (The Landing Zone) ---
resource "aws_s3_bucket" "uploads_bucket" {
  bucket        = "bill-e-uploads-${random_id.suffix.hex}"
  force_destroy = true 
}

resource "aws_s3_bucket_versioning" "uploads_versioning" {
  bucket = aws_s3_bucket.uploads_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

# --- 2. DYNAMODB TABLE (The Ledger) ---
resource "aws_dynamodb_table" "expenses_table" {
  name         = "BillE_Expenses"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "ReceiptID"

  attribute {
    name = "ReceiptID"
    type = "S" 
  }

  tags = {
    Environment = "Dev"
    Project     = "Bill-E"
  }
}

# --- 3. SQS QUEUES (The Buffer Layer) ---
resource "aws_sqs_queue" "dlq" {
  name = "bill-e-dlq"
}

resource "aws_sqs_queue" "ingest_queue" {
  name                      = "bill-e-ingest-queue"
  delay_seconds             = 0
  max_message_size          = 262144 
  message_retention_seconds = 86400  
  receive_wait_time_seconds = 10     

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 3 
  })
}

# --- 4. PERMISSIONS (Allow S3 -> SQS) ---
resource "aws_sqs_queue_policy" "allow_s3_to_sqs" {
  queue_url = aws_sqs_queue.ingest_queue.id
  policy    = data.aws_iam_policy_document.s3_to_sqs.json
}

data "aws_iam_policy_document" "s3_to_sqs" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["s3.amazonaws.com"]
    }
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.ingest_queue.arn]
    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_s3_bucket.uploads_bucket.arn]
    }
  }
}

# --- UTILITIES ---
resource "random_id" "suffix" {
  byte_length = 4
}

# --- OUTPUTS ---
output "bucket_name" {
  value = aws_s3_bucket.uploads_bucket.id
}

output "queue_url" {
  value = aws_sqs_queue.ingest_queue.url
}

output "api_endpoint" {
  value = "${aws_apigatewayv2_api.main.api_endpoint}/expenses"
}

# --- 5. THE TRIGGER (Connecting S3 to SQS) ---
resource "aws_s3_bucket_notification" "bucket_notification" {
  bucket = aws_s3_bucket.uploads_bucket.id

  queue {
    queue_arn     = aws_sqs_queue.ingest_queue.arn
    events        = ["s3:ObjectCreated:*"]
    # No filter_suffix here means ALL files are accepted!
  }
}

# --- 6. THE WORKER (Lambda Function) ---
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "../lambda/processor.py"
  output_path = "processor_payload.zip"
}

resource "aws_iam_role" "lambda_role" {
  name = "bill-e-processor-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "lambda_policy" {
  name = "bill-e-processor-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = aws_sqs_queue.ingest_queue.arn
      },
      {
        Effect = "Allow"
        Action = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.uploads_bucket.arn}/*"
      },
      {
        Effect = "Allow"
        Action = ["dynamodb:PutItem", "dynamodb:Scan", "dynamodb:Query"]
        Resource = aws_dynamodb_table.expenses_table.arn
      }
    ]
  })
}

resource "aws_lambda_function" "processor" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "bill-e-processor"
  role             = aws_iam_role.lambda_role.arn
  handler          = "processor.lambda_handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime          = "python3.9"
  
  timeout          = 30  

  environment {
    variables = {
      TABLE_NAME    = aws_dynamodb_table.expenses_table.name
      OCR_API_KEY   = var.ocr_api_key
      SNS_TOPIC_ARN = aws_sns_topic.alerts.arn  # Passed to Python here
    }
  }
}

# --- 7. THE TRIGGER (Connecting SQS to Lambda) ---
resource "aws_lambda_event_source_mapping" "sqs_trigger" {
  event_source_arn = aws_sqs_queue.ingest_queue.arn
  function_name    = aws_lambda_function.processor.arn
  batch_size       = 1
}

# --- 8. THE READER (Lambda Function) ---
data "archive_file" "reader_zip" {
  type        = "zip"
  source_file = "../lambda/reader.py"
  output_path = "reader_payload.zip"
}

resource "aws_lambda_function" "reader" {
  filename         = data.archive_file.reader_zip.output_path
  function_name    = "bill-e-reader"
  role             = aws_iam_role.lambda_role.arn
  handler          = "reader.lambda_handler"
  source_code_hash = data.archive_file.reader_zip.output_base64sha256
  runtime          = "python3.9"
}

resource "aws_lambda_permission" "api_gw" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.reader.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

# --- 9. THE API GATEWAY ---
resource "aws_apigatewayv2_api" "main" {
  name          = "bill-e-api"
  protocol_type = "HTTP"
  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["Content-Type"]
  }
}

resource "aws_apigatewayv2_stage" "dev" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_apigatewayv2_integration" "lambda_integration" {
  api_id           = aws_apigatewayv2_api.main.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.reader.invoke_arn
}

resource "aws_apigatewayv2_route" "get_expenses" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /expenses" 
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

# --- 11. THE SNITCH (SNS Email Alerts) ---

# A. Create the Topic
resource "aws_sns_topic" "alerts" {
  name = "bill-e-high-risk-alerts"
}

# B. Subscribe your Email (Securely)
resource "aws_sns_topic_subscription" "email_target" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email  # Reads from terraform.tfvars
}

# C. Give Lambda Permission to Send Emails
resource "aws_iam_role_policy" "sns_policy" {
  name = "bill-e-sns-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "sns:Publish"
        Resource = aws_sns_topic.alerts.arn
      }
    ]
  })
}