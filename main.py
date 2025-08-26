import logfire


from tasks.transcribe_image import transcribe_image
from tasks.tool_test import tool_test



logfire.configure()  
logfire.instrument_pydantic_ai()

if __name__ == "__main__":
    tool_test()

    # print("Available actions:")
    # print("1. Transcribe image")
    # action = input("What do you want to do? ")

    # if action == "1":
    #     image_path = input("Enter the path to the image: ")
    #     result = transcribe_image(image_path)
    #     print(result)
    # else:
    #     print("Invalid action")
