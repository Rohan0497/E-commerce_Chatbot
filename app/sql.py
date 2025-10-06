import sqlite3
import pandas as pd
from groq import Groq
import re
from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv()
GROQ_MODEL = os.getenv('GROQ_MODEL')
db_path = Path(__file__).parent / "db.sqlite"


client_sql = Groq()

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
    
    chat_completion = client_sql.chat.completions.create(
    model= os.environ['GROQ_MODEL'],
        messages=[
            {
                "role": "system",
                "content": sql_prompt
            },
            {
                "role": "user",
                "content": question
            }
        ],
        temperature=0.2,
        max_tokens=1024,

    )
    return chat_completion.choices[0].message.content



def run_query(query):
    if query.strip().upper().startswith('SELECT'):
    
        with sqlite3.connect(db_path) as conn:
            df = pd.read_sql_query(query,conn)
            return df

comprehension_prompt = """You are an expert in understanding the context of the question and replying based on the data pertaining to the question provided. You will be provided with Question: and Data:. The data will be in the form of an array or a dataframe or dict. Reply based on only the data provided as Data for answering the question asked as Question. Do not write anything like 'Based on the data' or any other technical words. Just a plain simple natural language response.
The Data would always be in context to the question asked. For example is the question is “What is the average rating?” and data is “4.3”, then answer should be “The average rating for the product is 4.3”. So make sure the response is curated with the question and data. Make sure to note the column names to have some context, if needed, for your response.
There can also be cases where you are given an entire dataframe in the Data: field. Always remember that the data field contains the answer of the question asked. All you need to do is to always reply in the following format when asked about a product: 
Produt title, price in indian rupees, discount, and rating, and then product link. Take care that all the products are listed in list format, one line after the other. Not as a paragraph.
For example:
1. Campus Women Running Shoes: Rs. 1104 (35 percent off), Rating: 4.4 <link>
2. Campus Women Running Shoes: Rs. 1104 (35 percent off), Rating: 4.4 <link>
3. Campus Women Running Shoes: Rs. 1104 (35 percent off), Rating: 4.4 <link>

"""

def sql_chain(question):
    sql_query = generate_sql_query(question)
    pattern = "<SQL>(.*?)</SQL>"
    matches = re.findall(pattern, sql_query, re.DOTALL)

    if len(matches) == 0:
        return "Sorry, LLM is not able to generate a query for your question"
    
    print(matches[0].strip())
    response = run_query(matches[0].strip())

    if response is None:
        return "Sorry, there was a problem executing SQL query"

    context =  response.to_dict(orient='records')
    answer = data_comprehension(question, context)
    return answer

def data_comprehension(question,context):
    
    completion = client_sql.chat.completions.create(
    model= os.environ['GROQ_MODEL'],
        messages=[
            {
                "role": "system",
                "content": comprehension_prompt
            },
            {
                "role": "user",
                "content": f"QUESTION : {question}, DATA : {context}"
            }
            ],
        temperature=0.2,
        # max_completion_tokens=1024,

    )
    return completion.choices[0].message.content

if __name__ == "__main__":
    # query = "SELECT * FROM product LIMIT 5"
    # df = run_query(query)
    # pass
    question = "All Nike shoes with rating higher than 4.8"
    # sql_query = generate_sql_query(question)
    # print(sql_query)

    answer = sql_chain(question)
    print(answer)
    # print(db_path)