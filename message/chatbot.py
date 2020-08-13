import requests
import config as cfg


class ChatBot:
    def send(self, text):
        params = {'chat_id': cfg.chatbot['chat_id'], 'text': text, 'parse_mode': 'HTML'}
        resp = requests.post('https://api.telegram.org/{}/sendMessage'.format(cfg.chatbot['bot_token']), params)
        resp.raise_for_status()
