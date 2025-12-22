# 🧾 Bill-E: AI-Powered Financial Auditor

![Python](https://img.shields.io/badge/Python-3.13-blue?style=for-the-badge&logo=python)
![AWS](https://img.shields.io/badge/AWS-S3%20%7C%20DynamoDB-orange?style=for-the-badge&logo=amazon-aws)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

**Bill-E** is a serverless financial pipeline that automates the digitization of physical receipts. It uses **Computer Vision (OCR)** to extract unstructured text from images, applies custom Python regex logic to isolate financial totals (filtering out noise like GST IDs and dates), and stores the structured audit records in **AWS DynamoDB**.

##  Architecture Flow

```mermaid
graph LR
    A[Receipt Image] -->|Upload| B(AWS S3 Bucket)
    B -->|Trigger| C{Python Audit Script}
    C -->|API Request| D[OCR.space AI Service]
    D -->|Raw Text| C
    C -->|Regex Logic| E[Clean Data JSON]
    E -->|Store| F[(AWS DynamoDB)]
```
## Tech Stack
* *Cloud Core:* AWS S3 (Storage), AWS DynamoDB (NoSQL Database)

* *Infrastructure as Code (IaC):* Boto3 (Python SDK) for provisioning resources.

* *AI/ML:* Optical Character Recognition (OCR) via REST API.

* *Language:* Python 3.13 (Regex, Request handling).

## Key Features
* *Auto-Provisioning:* The entire cloud environment (Buckets, Tables) is built via code (setup_infra.py), not manually.

* *Smart Parsing:* Custom algorithm intelligently distinguishes between "Total Amount", "Phone Numbers", and "Years" (e.g., distinguishing 2025.00 from $440.00).

* *Secure:* API Keys and Secrets are managed via git-ignored configuration files.

## Setup & Installation
**1. Clone the Repo**

```Bash

git clone [https://github.com/Tannishaa/bill-e-audit.git](https://github.com/Tannishaa/bill-e-audit.git)
cd bill-e-audit
```
2. Initialize Virtual Environment

```Bash

python -m venv venv
# Windows:
.\venv\Scripts\Activate.ps1
# Mac/Linux:
source venv/bin/activate
```
**3. Install Dependencies**

```Bash

pip install -r requirements.txt
```
**4. Configure Secrets:** Create a config.py file in the root directory:

```Python

# config.py
BUCKET_NAME = "your-unique-bucket-name"
TABLE_NAME = "ExpenseLedger"
REGION = "ap-south-1"
OCR_API_KEY = "your_ocr_space_key"
```
##  Usage
**Step 1: Build the Cloud Infrastructure:** Run this once to create your S3 Bucket and DynamoDB Table.

```Bash

python setup_infra.py
```
**Step 2: Upload a Receipt:** Place your image as receipt.png and run:

```Bash

python upload.py
```
**Step 3: Run the Audit:** This extracts the data and saves it to the database.

```Bash

python audit.py
```


