# FoodGenie
This was a full stack project I completed during the 2025 DubHacks Hackathon.

## 🥗 FoodGenie: The Personalized Nutrition Navigator

### 💡 Inspiration: The Consumer Problem
Today, going to the grocery store is an ordeal, an informational overload. Customers spend **huge** amounts of time agonizing over food labels, attempting to reconcile the facts with their own personal wellness goals and dietary restrictions. **FoodGenie** closes this gap by transforming obscure label data into immediate, personalized, and actionable health recommendations.

### 🎯 What It Does: AI-Powered Personalized Analysis
**FoodGenie** is a smart health assistant that provides instant, evidence-based recommendations tailored to the user's health profile.

- **Multimodal Input**: The user simply uploads a single photo containing both the nutrition facts panel and the product barcode.

- **Intelligent Data Fusion**: It uses Pyzbar for reliable barcode scanning and OCR for label text, then fuses this data with information from external nutrition APIs.

- **RAG-Enhanced Analysis**: The extracted data is sent to an AWS Bedrock RAG agent (Grounding provided by FDA/USDA guidelines).

- **Personalized Verdict**: The agent returns a detailed summary that directly checks the product against the user's health goals, allergies, and chronic conditions, providing a safety verdict and suggesting alternatives.

### ⚙️ How We Built It: A Serverless AWS Ecosystem
This application is a full-stack, serverless solution demonstrating integrating multiple AWS services:

**Frontend**: Python/Streamlit for a fast, intuitive UI.

**Core AI Logic**: A multi-step pipeline utilizing AWS Bedrock for the RAG-based, personalized analysis.

**Data Persistence**: MongoDB Atlas for saving and retrieving user history, allowing them to track past product analyses.

**Backend & Orchestration**: AWS API Gateway integrated with Lamba handles the complex multimodal data flow, API calls, and interaction with the AI.

**Image Processing**: Deployed with CV libraries (Pyzbar and Pillow) for robust barcode detection. Utilized Amazon Textract for OCR Recognition of nutrition facts.

### 🚧 Challenges
**Challenge**: Initial OCR efforts failed dramatically due to angled or poor-quality barcodes.

**Solution**: We pivoted to a Computer Vision/CV-based solution (Pyzbar) for barcode detection, making the entire system robust against real-world user photography. We successfully integrated a cohesive chain of AWS services (Bedrock, Lambda, MongoDB) to deliver a single, useful output.

### 🚀 What's Next For FoodGenie
The future holds much in store for tailored AI assistants:

**Extended RAG**: Can integrate a database of known food alternatives to provide better, geo-located product recommendations.

**Real-Time CV**: Implement advanced CV to better detect and localize nutritional text blocks, reducing reliance on barcode availability and improving data accuracy across diverse packaging formats.

**E-commerce Integration**: Use the personalized data to instantly filter and rate products within online grocery platforms

**Health Customization**: Can personalize recommendations further by integrating more detailed health information for users, and connecting with their digital health app.
