from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain.agents import create_agent
from tools import search_flights, find_cheapest_dates, compare_routes
import os

load_dotenv()

## LLM
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0,
    groq_api_key=os.getenv("GROQ_API_KEY")
)

## Tools
tools = [search_flights, find_cheapest_dates, compare_routes]

## Agent
agent_executor = create_agent(
    model=llm,
    tools=tools,
    system_prompt="You are a helpful flight search assistant. Use the available tools to search for flights, find the cheapest dates, and compare routes. Always provide clear, structured results to the user."
)