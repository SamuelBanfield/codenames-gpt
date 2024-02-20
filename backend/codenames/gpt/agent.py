import openai

from codenames.options import OPEN_AI_KEY, GPT_MODEL

class GPTAgent:

    def __init__(self):
        self.client = openai.OpenAI(
            api_key=OPEN_AI_KEY,
        )

    def get_clue(self, words_to_guess, words_to_avoid):
        print(f"Getting clue from GPT to link {words_to_guess}")
        response = self.client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are playing codenames and it's you turn to give a clue. Return the clue, followed by the number of words it links to, e.g: CLUE,3. Make sure that your clue links only to your teams words, and not to words from the other team. The clue doesn't need to link to all of your teams words."
                },
                {
                    "role": "user",
                    "content": f"Your teams words that you must link are [{','.join(words_to_guess)}] and the other teams words that you MUST NOT link to are [{','.join(words_to_avoid)}]"
                },
            ]
        )

        if response.choices[0].finish_reason != "stop":
            print(f"Failed to get response from chat gpt: {response.choices[0].finish_reason}")

        print(f"GPT clue: {response.choices[0].message.content}")

        raw_word, raw_number = response.choices[0].message.content.split(",")
        cleaned_number = ""
        for char in raw_number:
            if char in "0987654321":
                cleaned_number += char
        cleaned_word = ""
        for char in raw_word:
            if char.lower() in "abcdefghijklmnopqrstuvwxyz":
                cleaned_word += char.upper()
        return cleaned_word.upper(), int(cleaned_number)

    def guess(self, clue, words):
        print(f"GPT guessing for clue {clue}")
        prompt = f"The words are [{','.join(words)}] and the clue word is '{clue[0]}' and you must guess {clue[1]} words"
        print(prompt)
        response = self.client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are playing codenames and it's you turn to guess a word. Return the words you think are most closely linked to the clue provided separated by commas on a single line e.g: WORD1,WORD2,WORD3"
                },
                {
                    "role": "user",
                    "content": f"The possible words are [{','.join(words)}], you must choose the {clue[1]} words from the list I have given you the link most closely to '{clue[0]}'. Make sure your guesses are from the list [{','.join(words)}], and all link to the clue '{clue[0]}'"
                },
            ]
        )
        if response.choices[0].finish_reason != "stop":
            print(f"Failed to get response from chat gpt: {response.choices[0].finish_reason}")

        guess = response.choices[0].message.content
        
        print(f"GPT guessed: {guess}")
        assumed_guesses = [word.strip() for word in guess.split(',')]
        lowered = [word.replace(" ", "").lower() for word in words]
        
        allowed_guesses = [word for word in assumed_guesses if word.replace(" ", "").lower() in lowered][:int(clue[1])]
        print(f"Intepreted as guessing: {allowed_guesses}")
        return allowed_guesses
