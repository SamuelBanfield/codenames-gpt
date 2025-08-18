import time
import openai
import logging
from typing import List, Tuple

from codenames.model import CodenamesConnection
from codenames.options import OPEN_AI_KEY, GPT_MODEL, VERBOSE_LOGGING

SYSTEM_PROMPT_CLUE = (
    "You are playing codenames and it's your turn to give a clue. "
    "Return the clue, followed by the number of words it links to, e.g: CLUE,3. "
    "It is VERY IMPORTANT you say ONLY the clue word, followed by a comma, and then the number of words it links to as a digit, e.g. CLUE,2 or GREEN,4"
)
SYSTEM_PROMPT_GUESS = (
    "You are playing codenames and it's your turn to guess a word. "
    "Return the words you think are most closely linked to the clue provided separated by commas on a single line e.g: WORD1,WORD2,WORD3"
)


class GPTConnection(CodenamesConnection):
    
    async def send(self, message: dict):
        '''No op for AI'''
        return

class ChatGPT:
    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=OPEN_AI_KEY)

    async def get_clue(self, words_to_guess: List[str], words_to_avoid: List[str]) -> Tuple[str, int]:
        logging.debug(f"Getting clue from GPT to link {words_to_guess}")
        start = time.time()
        response = await self._get_gpt_response(
            SYSTEM_PROMPT_CLUE,
            f"Your team's words that you must link are [{','.join(words_to_guess)}] and the other team's words that you MUST NOT link to are [{','.join(words_to_avoid)}]"
        )
        logging.debug(f"GPT response time: {time.time() - start}")

        if response.choices[0].finish_reason != "stop":
            logging.error(f"Failed to get response from chat GPT: {response.choices[0].finish_reason}")
            return "", 0

        content = response.choices[0].message.content
        if content is None:
            logging.error("GPT response content is None")
            return "", 0
            
        clue, number = self._parse_clue_response(content)
        logging.debug(f"GPT clue: {clue}, {number}")
        return clue, number

    async def guess(self, clue: Tuple[str, int], words: List[str]) -> List[str]:
        logging.debug(f"GPT guessing for clue {clue}")
        response = await self._get_gpt_response(  # Make this async
            SYSTEM_PROMPT_GUESS,
            f"The possible words are [{','.join(words)}], you must choose the {clue[1]} words from the list I have given you that link most closely to '{clue[0]}'. Make sure your guesses are from the list [{','.join(words)}], and all link to the clue '{clue[0]}'"
        )

        if response.choices[0].finish_reason != "stop":
            logging.error(f"Failed to get response from chat GPT: {response.choices[0].finish_reason}")
            return []

        content = response.choices[0].message.content
        if content is None:
            logging.error("GPT response content is None")
            return []
            
        guesses = self._parse_guess_response(content, words, clue[1])
        logging.debug(f"GPT guessed: {guesses}")
        return guesses

    async def _get_gpt_response(self, system_prompt: str, user_prompt: str):
        try:
            return await self.client.chat.completions.create(
                model=GPT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )
        except Exception as e:
            logging.error(f"Error getting GPT response: {e}")
            raise

    def _parse_clue_response(self, content: str) -> Tuple[str, int]:
        try:
            raw_word, raw_number = content.split(",")
            cleaned_word = ''.join(char.upper() for char in raw_word if char.isalpha())
            cleaned_number = int(''.join(char for char in raw_number if char.isdigit()))
            return cleaned_word, cleaned_number
        except ValueError as e:
            logging.error(f"Error parsing clue response: {e}")
            return "", 0

    def _parse_guess_response(self, content: str, words: List[str], num_guesses: int) -> List[str]:
        assumed_guesses = [word.strip() for word in content.split(',')]
        lowered = [word.replace(" ", "").lower() for word in words]
        allowed_guesses = [word for word in assumed_guesses if word.replace(" ", "").lower() in lowered][:num_guesses]
        logging.debug(f"Interpreted as guessing: {allowed_guesses}")
        return allowed_guesses
