'use client'

import { useState } from "react";
import { uploadReceipt } from "../actions";

export default function AdminZone() {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState("");

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setStatus("Uploading to S3...");
    const formData = new FormData();
    formData.append("file", file);

    const result = await uploadReceipt(formData);
    setStatus(result.message);
  };

  return (
    <div className="bg-gray-900 p-6 rounded-lg border border-gray-800 shadow-[0_0_15px_rgba(59,130,246,0.1)]">
      <div className="mb-6">
        <p className="text-blue-400 font-medium">Upload Pipeline Ready</p>
        <p className="text-gray-500 text-sm mt-1">Select a receipt image to send it directly to the AWS SQS queue.</p>
      </div>

      <form onSubmit={handleUpload} className="flex flex-col gap-4 max-w-md">
        <input 
          type="file" 
          accept="image/png, image/jpeg"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
          className="block w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-700"
        />
        <button 
          type="submit"
          disabled={!file}
          className="bg-blue-600 disabled:bg-gray-700 hover:bg-blue-700 px-4 py-2 rounded text-white font-medium transition"
        >
          Upload to Cloud Pipeline
        </button>
        {status && <p className="text-blue-400 text-sm mt-2">{status}</p>}
      </form>
    </div>
  );
}