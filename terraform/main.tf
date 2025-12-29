provider "aws" {
  region = "ap-south-1"  # Mumbai Region
}

# --- 1. S3 BUCKET (The Landing Zone) ---
# Why: Standard storage for receipts. We enable versioning so accidental
# overwrites (same filename) don't destroy data—a key data integrity practice.
resource "aws_s3_bucket" "uploads_bucket" {
  bucket = "bill-e-uploads-${random_id.suffix.hex}"
  force_destroy = true # Allows deleting bucket even if it has files (for dev only)
}

resource "aws_s3_bucket_versioning" "uploads_versioning" {
  bucket = aws_s3_bucket.uploads_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

# --- 2. DYNAMODB TABLE (The Ledger) ---
# Why: NoSQL is perfect here because receipt structures vary.
# On-Demand billing (PAY_PER_REQUEST) is cheaper for sporadic traffic.
resource "aws_dynamodb_table" "expenses_table" {
  name         = "BillE_Expenses"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "ReceiptID"

  attribute {
    name = "ReceiptID"
    type = "S" # String
  }

  tags = {
    Environment = "Dev"
    Project     = "Bill-E"
  }
}

# --- 3. SQS QUEUES (The Buffer Layer) ---
# Why: This separates the 'Upload' action from the 'Process' action.
# If 1,000 receipts arrive at once, they wait in line here instead of crashing the system.

# A. Dead Letter Queue (DLQ)
# If a message fails to process 3 times (corrupt file?), it goes here so we don't lose it.
resource "aws_sqs_queue" "dlq" {
  name = "bill-e-dlq"
}

# B. Main Ingestion Queue
resource "aws_sqs_queue" "ingest_queue" {
  name                      = "bill-e-ingest-queue"
  delay_seconds             = 0
  max_message_size          = 262144 # 256 KB
  message_retention_seconds = 86400  # 1 day retention
  receive_wait_time_seconds = 10     # Long polling (cheaper/faster)

  # Connects this queue to the DLQ above
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 3 # Try 3 times before giving up
  })
}

# --- 4. PERMISSIONS (The Security) ---
# Allow S3 to send messages to SQS
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
# Generates a random suffix so your bucket name is globally unique
resource "random_id" "suffix" {
  byte_length = 4
}

# --- OUTPUTS ---
# Prints these values to your terminal after deploy
output "bucket_name" {
  value = aws_s3_bucket.uploads_bucket.id
}

output "queue_url" {
  value = aws_sqs_queue.ingest_queue.url
}

# --- 5. THE TRIGGER (Connecting S3 to SQS) ---
# Why: This creates the actual "Event." 
# When a file ending in .jpg, .png, or .pdf hits the bucket -> Send to Queue.
resource "aws_s3_bucket_notification" "bucket_notification" {
  bucket = aws_s3_bucket.uploads_bucket.id

  queue {
    queue_arn     = aws_sqs_queue.ingest_queue.arn
    events        = ["s3:ObjectCreated:*"]
    filter_suffix = ".jpg"
  }
  
  queue {
    queue_arn     = aws_sqs_queue.ingest_queue.arn
    events        = ["s3:ObjectCreated:*"]
    filter_suffix = ".png"
  }

  queue {
    queue_arn     = aws_sqs_queue.ingest_queue.arn
    events        = ["s3:ObjectCreated:*"]
    filter_suffix = ".pdf"
  }
}

# --- 6. THE WORKER (Lambda Function) ---

# A. Zip the Python code (Terraform does this automatically!)
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "../lambda/processor.py"  # Path to your python file
  output_path = "processor_payload.zip"
}

# B. Create the IAM Role (The "ID Card" for the function)
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


# C. Attach Permissions (S3, SQS, Logs, Textract, DynamoDB Read/Write)
resource "aws_iam_role_policy" "lambda_policy" {
  name = "bill-e-processor-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # 1. Logging
      {
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      },
      # 2. Queue Reading
      {
        Effect = "Allow"
        Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = aws_sqs_queue.ingest_queue.arn
      },
      # 3. S3 Reading
      {
        Effect = "Allow"
        Action = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.uploads_bucket.arn}/*"
      },
      # 4. AI (Textract)
      {
        Effect = "Allow"
        Action = ["textract:DetectDocumentText", "textract:AnalyzeDocument"]
        Resource = "*"
      },
      # 5. DYNAMODB PERMISSIONS (UPDATED: Now includes Scan/Query)
      {
        Effect = "Allow"
        Action = ["dynamodb:PutItem", "dynamodb:Scan", "dynamodb:Query"]
        Resource = aws_dynamodb_table.expenses_table.arn
      }
    ]
  })
}

# D. The Actual Function
resource "aws_lambda_function" "processor" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "bill-e-processor"
  role             = aws_iam_role.lambda_role.arn
  handler          = "processor.lambda_handler" # File.Method
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime          = "python3.9"
  timeout          = 30 # Give it 30 seconds to run
}

# --- 7. THE TRIGGER (Connecting SQS to Lambda) ---
resource "aws_lambda_event_source_mapping" "sqs_trigger" {
  event_source_arn = aws_sqs_queue.ingest_queue.arn
  function_name    = aws_lambda_function.processor.arn
  batch_size       = 1 # Process 1 receipt at a time (safer for now)
}

# --- 8. THE READER (Lambda Function) ---

# A. Zip the Reader Code
data "archive_file" "reader_zip" {
  type        = "zip"
  source_file = "../lambda/reader.py"
  output_path = "reader_payload.zip"
}

# B. Create the Reader Function
resource "aws_lambda_function" "reader" {
  filename         = data.archive_file.reader_zip.output_path
  function_name    = "bill-e-reader"
  role             = aws_iam_role.lambda_role.arn # Re-using the same role for simplicity
  handler          = "reader.lambda_handler"
  source_code_hash = data.archive_file.reader_zip.output_base64sha256
  runtime          = "python3.9"
}

# C. Allow API Gateway to invoke this Lambda
resource "aws_lambda_permission" "api_gw" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.reader.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

# --- 9. THE API GATEWAY (The Public Door) ---

# A. Create the API
resource "aws_apigatewayv2_api" "main" {
  name          = "bill-e-api"
  protocol_type = "HTTP"
  
  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["Content-Type"]
  }
}

# B. Create a "Stage" (The environment, e.g., 'dev' or 'prod')
resource "aws_apigatewayv2_stage" "dev" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default" # Makes the URL shorter (no /dev needed)
  auto_deploy = true
}

# C. Create the Integration (Connecting API -> Lambda)
resource "aws_apigatewayv2_integration" "lambda_integration" {
  api_id           = aws_apigatewayv2_api.main.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.reader.invoke_arn
}

# D. Create the Route (The URL Path)
# This means: "When someone visits GET /expenses, run the Lambda"
resource "aws_apigatewayv2_route" "get_expenses" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /expenses" 
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

# --- 10. NEW OUTPUT (The URL) ---
output "api_endpoint" {
  value = "${aws_apigatewayv2_api.main.api_endpoint}/expenses"
}