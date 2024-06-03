import argparse
import datetime
import logging
import json
import websockets
import api

from websocket import WebSocket
from cmd_type import CHZZK_CHAT_CMD


class ChzzkChat:
    def __init__(self, streamer: str, file_path: str, start_time: float, cookies, logger):
        self.streamer = streamer
        self.file_path = file_path
        self.start_time = datetime.datetime.fromtimestamp(start_time)
        self.cookies = cookies
        self.logger = logger

        self.sid = None
        self.userIdHash = api.fetch_userIdHash(self.cookies)
        self.chatChannelId = api.fetch_chatChannelId(self.streamer)
        self.channelName = api.fetch_channelName(self.streamer)
        self.accessToken, self.extraToken = api.fetch_accessToken(self.chatChannelId, self.cookies)

        self.connect()

    def connect(self):
        self.chatChannelId = api.fetch_chatChannelId(self.streamer)
        self.accessToken, self.extraToken = api.fetch_accessToken(self.chatChannelId, self.cookies)

        sock = WebSocket()
        sock.connect('wss://kr-ss1.chat.naver.com/chat')
        print(f'{self.channelName} 채팅창에 연결 중 .', end="")

        default_dict = {
            "ver": "2",
            "svcid": "game",
            "cid": self.chatChannelId,
        }

        send_dict = {
            "cmd": CHZZK_CHAT_CMD['connect'],
            "tid": 1,
            "bdy": {
                "uid": self.userIdHash,
                "devType": 2001,
                "accTkn": self.accessToken,
                "auth": "SEND"
            }
        }

        sock.send(json.dumps(dict(send_dict, **default_dict)))
        sock_response = json.loads(sock.recv())
        self.sid = sock_response['bdy']['sid']
        print(f'\r{self.channelName} 채팅창에 연결 중 ..', end="")

        send_dict = {
            "cmd": CHZZK_CHAT_CMD['request_recent_chat'],
            "tid": 2,

            "sid": self.sid,
            "bdy": {
                "recentMessageCount": 50
            }
        }

        sock.send(json.dumps(dict(send_dict, **default_dict)))
        sock.recv()
        print(f'\r{self.channelName} 채팅창에 연결 중 ...')

        self.sock = sock

        if self.sock.connected:
            print('연결 완료')
        else:
            raise ValueError('오류 발생')

    def run(self):
        while True:
            try:
                try:
                    raw_message = self.sock.recv()

                except KeyboardInterrupt:
                    break

                except websockets.WebSocketException:
                    self.connect()
                    raw_message = self.sock.recv()

                raw_message = json.loads(raw_message)
                chat_cmd = raw_message['cmd']

                if chat_cmd == CHZZK_CHAT_CMD['ping']:
                    self.sock.send(
                        json.dumps({
                            "ver": "2",
                            "cmd": CHZZK_CHAT_CMD['pong']
                        })
                    )

                    if self.chatChannelId != api.fetch_chatChannelId(self.streamer):  # 방송 시작시 chatChannelId가 달라지는 문제
                        self.connect()

                    continue

                if chat_cmd == CHZZK_CHAT_CMD['chat']:
                    chat_type = '채팅'

                elif chat_cmd == CHZZK_CHAT_CMD['donation']:
                    chat_type = '후원'

                else:
                    continue

                for chat_data in raw_message['bdy']:
                    if chat_data['uid'] == 'anonymous':
                        nickname = '익명의 후원자'

                    else:
                        try:
                            profile_data = json.loads(chat_data['profile'])
                            nickname = profile_data["nickname"]

                            if 'msg' not in chat_data:
                                continue

                        except (json.JSONDecodeError, KeyError):
                            continue

                    msg_time = datetime.datetime.fromtimestamp(chat_data['msgTime'] / 1000)
                    msg_time_str = datetime.datetime.strftime(msg_time, '%Y-%m-%d %H:%M:%S')

                    elapsed_time = msg_time - self.start_time
                    elapsed_time_str = str(elapsed_time).split('.')[0]

                    self.logger.info(f'[{msg_time_str} (+{elapsed_time_str})][{chat_type}] {nickname} : {chat_data["msg"]}')

            except:
                pass


def get_logger(file_path):
    formatter = logging.Formatter('%(message)s')

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    file_handler = logging.FileHandler(file_path, mode="w")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--streamer_id', type=str, required=True)
    parser.add_argument('--file_path', type=str, default='./chat.txt')
    parser.add_argument('--start_time', type=float, default=0)
    args = parser.parse_args()

    with open('cookies.json') as f:
        cookies = json.load(f)

    if not args.start_time:
        args.start_time = datetime.datetime.now().timestamp()

    logger = get_logger(args.file_path)
    chzzkchat = ChzzkChat(args.streamer_id, args.file_path, args.start_time, cookies, logger)

    chzzkchat.run()
