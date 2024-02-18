import json
import pathlib
import openai

properties_file_path = pathlib.Path(__file__).parent.parent.parent / ".properties.json"

try:
    with open(properties_file_path) as property_file:
        properties = json.load(property_file)
except FileNotFoundError as e:
    raise FileNotFoundError(f"Could not find .properties.json file: {e}")

MODEL = "gpt-3.5-turbo"

class GPTAgent:

    def __init__(self):
        self.client = openai.OpenAI(
            api_key=properties["openaiKey"],
        )

    def get_clue(self, words_to_guess, words_to_avoid):
        print(f"Getting clue from GPT to link {words_to_guess}")
        response = self.client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are playing codenames and it's you turn to give a clue. Return the clue, followed by the number of words it links to, e.g: CLUE,3. Make sure that your clue links only to your teams words, and not to words from the other team"},
                {"role": "user", "content": f"Your teams words that you must link are [{','.join(words_to_guess)}] and the other teams words that you MUST NOT link to are [{','.join(words_to_avoid)}]"},
            ]
        )

        if response.choices[0].finish_reason != "stop":
            print(f"Failed to get response from chat gpt: {response.choices[0].finish_reason}")

        print(f"GPT clue: {response.choices[0].message.content}")
        return response.choices[0].message.content.split(",")

    def guess(self, clue, words):
        print(f"GPT guessing for clue {clue}")
        prompt = f"The words are [{','.join(words)}] and the clue word is '{clue[0]}' and you must guess {clue[1]} words"
        print(prompt)
        response = self.client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are playing codenames and it's you turn to guess a word. Return the words you think are most closely linked to the clue provided separated by commas on a single line e.g: WORD1,WORD2,WORD3"},
                {"role": "user", "content": f"The possible words are [{','.join(words)}] and the clue word is '{clue[0]}' and you must guess {clue[1]} words from the list that link to this word. Order the words by how likely you think they are to be correct"},
            ]
        )
        if response.choices[0].finish_reason != "stop":
            print(f"Failed to get response from chat gpt: {response.choices[0].finish_reason}")

        print(f"GPT guessed: {response.choices[0].message.content}")
        return response.choices[0].message.content
        

# def test():
#     from codenames.model import generate_tiles

#     tiles = generate_tiles()

#     red_words = [tile.word for tile in tiles if tile.team == 'red']
#     other_words = [tile.word for tile in tiles if tile.team != 'red']
#     print(f"Red words: {red_words}")
#     print(f"Other words: {other_words}")

#     guesser = Guesser()

#     clue = guesser.get_clue(red_words, other_words)
#     print(f"Clue: {clue}")

#     print(guesser.guess(clue, [tile.word for tile in tiles]))
