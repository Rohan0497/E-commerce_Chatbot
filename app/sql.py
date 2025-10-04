import sqlite3
import pandas as pd
from groq import Groq

from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv()
GROQ_MODEL = os.getenv('GROQ_MODEL')
db_path = Path(__file__).parent / "db.sqlite"

sql_client = Groq()

sql_prompt = """You are an expert in understanding the database schema and generating SQL queries for a natural language question asked
pertaining to the data you have. The schema is provided in the schema tags. 
<schema> 
table: product 

fields: 
product_link - string (hyperlink to product)	
title - string (name of the product)	
brand - string (brand of the product)	
price - integer (price of the product in Indian Rupees)	
discount - float (discount on the product. 10 percent discount is represented as 0.1, 20 percent as 0.2, and such.)	
avg_rating - float (average rating of the product. Range 0-5, 5 is the highest.)	
total_ratings - integer (total number of ratings for the product)

</schema>
Make sure whenever you try to search for the brand name, the name can be in any case. 
So, make sure to use %LIKE% to find the brand in condition. Never use "ILIKE". 
Create a single SQL query for the question provided. 
The query should have all the fields in SELECT clause (i.e. SELECT *)

Just the SQL query is needed, nothing more. Always provide the SQL in between the <SQL></SQL> tags."""



def generate_sql_query(question):
    
    completion = sql_client.chat.completions.create(
    model= os.environ['GROQ_MODEL'],
        messages=[
            {
                "role": "user",
                "content": sql_prompt
            },
            {
                "role": "system",
                "content": question
            }
            ],
        temperature=0.2,
        max_completion_tokens=1024,

    )
    return completion.choices[0].message.content




def run_query(query):
    if query.strip().upper().startswith('SELECT'):
    
        with sqlite3.connect('db.sqlite') as conn:
            df = pd.read_sql_query(query,conn)
            return df
    
if __name__ == "__main__":
    # query = "SELECT * FROM product LIMIT 5"
    # df = run_query(query)
    # pass
    question = "All shoes with rating higher than 4.5 and total number of reviews greater than 500"
    sql_query = generate_sql_query(question)
    print(sql_query)