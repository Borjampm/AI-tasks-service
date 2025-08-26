from tasks.transcribe_image import transcribe_image


if __name__ == "__main__":
    print("Available actions:")
    print("1. Transcribe image")
    action = input("What do you want to do? ")

    if action == "1":
        image_path = input("Enter the path to the image: ")
        result = transcribe_image(image_path)
        print(result)
    else:
        print("Invalid action")
