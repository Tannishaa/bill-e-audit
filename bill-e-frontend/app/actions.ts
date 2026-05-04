'use server'

import { S3Client, PutObjectCommand } from "@aws-sdk/client-s3";
import { SNSClient, PublishCommand } from "@aws-sdk/client-sns";
import { DynamoDBClient, PutItemCommand } from "@aws-sdk/client-dynamodb";
import crypto from "crypto";

const s3 = new S3Client({ region: process.env.AWS_REGION });
const sns = new SNSClient({ region: process.env.AWS_REGION });
const dynamodb = new DynamoDBClient({ region: process.env.AWS_REGION });

export async function uploadReceipt(formData: FormData) {
  const file = formData.get('file') as File;
  if (!file) throw new Error("No file uploaded");

  const buffer = Buffer.from(await file.arrayBuffer());
  
  // Create the exact same SHA-256 hash used in processor.py
  const fileHash = crypto.createHash('sha256').update(buffer).digest('hex');

  try {
    // 1. Write "Queued" Breadcrumb to DynamoDB
    if (process.env.DYNAMODB_TABLE_NAME) {
      await dynamodb.send(new PutItemCommand({
        TableName: process.env.DYNAMODB_TABLE_NAME,
        Item: {
          "ReceiptID": { S: fileHash },
          "Filename": { S: file.name },
          "UploadDate": { S: new Date().toISOString() },
          "Status": { S: "Queued" },
          "ExtractedText": { S: "Awaiting OCR Engine..." },
          "RiskScore": { N: "0" }
        }
      }));
    }

    // 2. Drop into S3 to trigger the pipeline
    await s3.send(new PutObjectCommand({
      Bucket: process.env.S3_BUCKET_NAME,
      Key: file.name,
      Body: buffer,
      ContentType: file.type,
    }));

    return { success: true, message: `Receipt sent to queue!` };
  } catch (error) {
    console.error(error);
    return { success: false, message: "Upload failed." };
  }
}