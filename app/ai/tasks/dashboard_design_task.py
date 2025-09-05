from app.tasks.base_task import BaseTask
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
USER_ID = os.getenv('USER_ID')

class DashboardDesignTask(BaseTask):
    def __init__(self):
        self.__conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        self.__cur = self.__conn.cursor()
        self.__create_agent()

    def run(self, *args, **kwargs):
        pass

    def __create_agent(self):
        self.__agent = Agent(
            self.__model,
            instructions=self.__base_instructions()
        )

    def __base_instructions(self):
        return """
        You are an expert in HTML, CSS, and JavaScript. You will build small front visualizations based on requests from the user.
        The user will include its request in the <user> tag. Design data, such as viewport size, will be included in the <design> tag if provided.
        You must retrieve the data from the userbase to create the visualizations.
        You will output code inside <output> tags.
        """