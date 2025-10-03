import pandas as pd
from pathlib import Path
import chromadb
from dotenv import load_dotenv
from groq import Groq
import os
load_dotenv()

faq_path = Path(__file__).parent / "faq_data.csv"
chroma_client = chromadb.Client()
collection_name_faq = 'faqs'
groq_client = Groq()



def ingest_faq_data(path):
    if collection_name_faq not in [c.name for c in chroma_client.list_collections()]:
        print("Ingesting FAQ data into Chromadb...")
        collection = chroma_client.get_or_create_collection(
            name = collection_name_faq,
        )
        df = pd.read_csv(path)
        docs = df['question'].to_list()
        metadata = [{"answer" : ans}for ans in df['answer'].to_list()]

        ids = [f"id_{i}" for i in range(len(docs))]

        collection.add(
            documents = docs,
            metadatas = metadata,
            ids = ids
        )
        print(f"FAQ Data successfully ingested into Chroma collection: {collection_name_faq}")
    else:
        print(f"Collection {collection_name_faq} already exists!")

def get_relevant_qa(query):
    collection = chroma_client.get_collection(name = collection_name_faq)
    result = collection.query(
        query_texts = [query],
        n_results = 2
    )
    return result

def faq_chain(query):
    result = get_relevant_qa(query)
    context = " ".join([r.get("answer") for r in result["metadatas"][0]])
    answer = generate_answer(query, context)
    return answer



def generate_answer(query, context):
    prompt = f"""
    Given the following context and question, generate answer based on this context only.
    If the answer is not found in the context, kindly state "I don't know". Don't try to make up an answer.
    
    Question : {query}
    Context : {context}

    """
    completion = groq_client.chat.completions.create(
    model= os.environ['GROQ_MODEL'],
        messages=[
            {
                "role": "user",
                "content": prompt
            }
            ],
        # temperature=1,
        # max_completion_tokens=1024,
        # top_p=1,
        # stream=True,
        # stop=None
    )
    return completion.choices[0].message.content
    

if __name__ == "__main__":
    ingest_faq_data(faq_path)

    query = "What is your policy on defective products?"
    # results = get_relevant_qa(query)
    answer = faq_chain(query)
    print(answer)
    
    
    
    