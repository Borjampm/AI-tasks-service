import logfire
from ai_tasks.q_and_a import q_a_with_model

logfire.configure()  
logfire.instrument_pydantic_ai()

if __name__ == "__main__":
    print(q_a_with_model("What is the capital of France?"))