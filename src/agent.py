from src.core import answer_question


print("Infrastructure Agent")
print("Type 'exit' to quit")
print()

while True:

    question = input("> ").strip()

    if question.lower() in ["exit", "quit"]:
        break

    try:

        response = answer_question(question)

        print()
        print(response)
        print()

    except Exception as e:

        print()
        print(f"ERROR: {e}")
        print()
