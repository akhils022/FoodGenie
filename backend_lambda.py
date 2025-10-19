import logging, json, boto3
import os, uuid, datetime, base64, re, urllib3, textwrap

logger = logging.getLogger()
logger.setLevel(logging.INFO)
bucket_name = os.getenv("BUCKET_NAME")
knowledge_base_id = os.getenv("KNOWLEDGE_BASE_ID")
s3 = boto3.client('s3')
textract = boto3.client('textract')
bedrock_agent = boto3.client('bedrock-agent-runtime')

SYSTEM_PROMPT = """
You are a professional health and nutrition expert. Your primary goal is to provide a comprehensive, personalized analysis of a food product.

You have access to a **Knowledge Base containing FDA and USDA guidelines**, to support your analysis, dietary recommendations, and health ratings.

You will receive the product's nutritional information and the user's specific health goals and constraints (allergies, diet, macro targets).

Your response must be formatted in clear Markdown and contain the following sections:
1. Product Summary & Quick Facts
2. Personalized Health Analysis & Safety Check (Reference user goals/constraints)
3. Detailed Recommendations & Alternatives

Keep your tone warm and inviting, but descriptive and knowledgeable.
"""

def extract_nutrition_facts(text):
    def find_value(label, text):
        pattern = rf"{label}\s*([\d.]+)\s*(mg|g|mcg|kcal)?"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1))
        return None

    nutri_info = {
        "energy-kcal_value": find_value("Calories", text),
        "fat_value": find_value("Total Fat", text),
        "saturated-fat_value": find_value("Saturated Fat", text),
        "trans-fat_value": find_value("Trans Fat", text),
        "sodium_value": find_value("Sodium", text),
        "cholesterol_value": find_value("Cholesterol", text),
        "carbohydrates_value": find_value("Total Carbohydrate", text),
        "sugars_value": find_value("Total Sugars", text),
        "proteins_value": find_value("Protein", text),
    }

    logger.info(f"Nutrition Info Extracted: {nutri_info}")
    nutri_info = {k: v for k, v in nutri_info.items() if v is not None}
    return nutri_info

def barcode_foodfacts(barcode: str):
    http = urllib3.PoolManager()
    url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json?fields=product_name,brands,nutriments,ingredients_text,nutriscore_grade,categories,image_url"

    # Make GET request
    response = http.request("GET", url)
    if response.status != 200:
        logger.error(f"Error fetching barcode data")
        return None

    try:
        data = json.loads(response.data.decode("utf-8"))
    except Exception as e:
        logger.error(f"Error decoding response: {e}")
        return None

    if data.get("status") == 0:
        logger.error(f"Error fetching barcode data")
        return None

    product = data.get("product", {})
    logger.info(f"Open Food Facts response: {json.dumps(data)[:500]}")  # Log first 500 chars

    # Extract useful fields
    return {
        "product_name": product.get("product_name", "Unknown"),
        "brand": product.get("brands", "Unknown"),
        "nutriments": product.get("nutriments", {}),
        "ingredients_text": product.get("ingredients_text", "N/A"),
        "image_url": product.get("image_url", None),
        "nutriscore": product.get("nutriscore_grade", None),
        "categories": product.get("categories", None)
    }

def parse_facts(key):
    # Use Textract for OCR to understand nutrition facts
    response = textract.detect_document_text(
        Document={"S3Object": {"Bucket": bucket_name, "Name": key}})
    text_blocks = [item["Text"] for item in response["Blocks"] if item["BlockType"] == "LINE"]
    text = "\n".join(text_blocks)
    logger.info(f"Textract result: {text}")
    return text

def call_bedrock(product_info, barcode_used, user_preferences):
    model_id = "anthropic.claude-3-haiku-20240307-v1:0"

    # Create prompt
    if barcode_used:
        data_quality = ("The product information is highly detailed, derived from an API lookup, "
            "and includes product name, category, and precise nutrition facts.")
        analysis_focus_note = "Provide the full 4-section analysis, including the product name and alternatives."
    else:
        data_quality = (
            "The product information is based only on OCR output from a label image. "
            "The product name and category may be missing or approximate. Focus the analysis primarily on the raw nutrition facts."
        )
        analysis_focus_note = "Since full product details may be sparse, focus on 'Health Analysis'."

    user_msg = f"""
    --- START ANALYSIS REQUEST ---
    
    **Data Quality:** {data_quality}
    
    Product Information:
    {product_info}
    
    User Preferences and Goals:
    {user_preferences}
    
    Based on the information above, and using the FDA guidelines from your Knowledge Base, perform the analysis.
    
    {analysis_focus_note}
    
    Please provide a succinct, evidence-based analysis, with detailed dietary recommendations.
    """

    full_prompt = f"{SYSTEM_PROMPT}\n\n{user_msg}"

    try:
        response = bedrock_agent.retrieve_and_generate(
            input={"text": full_prompt},
            retrieveAndGenerateConfiguration={
                "knowledgeBaseConfiguration": {
                    "knowledgeBaseId": knowledge_base_id,
                    "modelArn": f"arn:aws:bedrock:us-west-2::foundation-model/{model_id}"
                },
                "type": "KNOWLEDGE_BASE"
            }
        )
        logger.info(json.dumps(response, indent=2))

        output_text = response["output"]["text"]
        return output_text.strip()

    except Exception as e:
        logger.error(f"ERROR: Can't invoke Knowledge Base. Reason: {e}")
        return "Sorry, I couldn't generate insights for that product. Please try again!"

def lambda_handler(event, context):
    logger.info("Received Event")

    # Extract parameters from input
    body = json.loads(event["body"])
    user_id = body["user"]
    user_context = body["user_context"]
    barcode = body["barcode"]
    filename = body["filename"]
    file_bytes = base64.b64decode(body["image"])
    logger.info(f"Received File {filename} from user {user_id}")

    # Upload image to S3 Bucket securely with unique id
    key = f"uploads/{user_id}/{filename}/{uuid.uuid4().hex}"
    s3.put_object(Bucket=bucket_name, Key=key, Body=file_bytes)
    logger.info(f"Uploaded file - Name: {filename}, Key: {key}, Time: {datetime.datetime.now()}")

    # Get information about product
    text = parse_facts(key)
    nutri_facts = extract_nutrition_facts(text)
    barcode_used = barcode is not ""
    if barcode_used:
        logger.info(f"Barcode detected {barcode}")
        barcode_data = barcode_foodfacts(barcode)
        product_info = textwrap.dedent(f"""
            Product Name: {barcode_data.get('product_name', 'Unknown')}
            Brand: {barcode_data.get('brand', 'Unknown')}
            Categories: {barcode_data.get('categories', 'N/A')}
            Nutriscore: {barcode_data.get('nutriscore', 'N/A')}
            Ingredients: {barcode_data.get('ingredients_text', 'N/A')}
            Nutrition Facts: {json.dumps(barcode_data.get('nutriments', {}), indent=2)}
            """)
    else:
        product_info = textwrap.dedent(f"""
            Nutrition Facts (extracted via OCR):
            {json.dumps(nutri_facts, indent=2)}
            """)

    response = call_bedrock(product_info, barcode_used, user_context)

    body = {"user": user_id, "response": response}
    if barcode_used:
        body["product_name"] = barcode_data.get('product_name', "Unknown")
        body["image_url"] = barcode_data.get('image_url', "")
        body["facts"] = barcode_data.get('nutriments', {})
    else:
        body["facts"] = nutri_facts

    # Format response
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(body)
    }