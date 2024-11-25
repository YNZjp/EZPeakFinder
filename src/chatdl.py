import requests
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


class TwitchChatDL:
    CLIENT_ID = "kd1unb4b3q4t58fwlpcbzcbnm76a8fp"
    API_URL = "https://gql.twitch.tv/gql"

    def __init__(self, video_id, num_threads=10):
        self.headers = {
            "Client-ID": self.CLIENT_ID,
            "Content-Type": "application/json"
        }
        if num_threads < 1 or num_threads > 99:
            raise ValueError("スレッド数は1から99の間で指定してください。")
        self.video_id = video_id
        self.num_threads = num_threads
        self.comments = []

    def get_video_info(self):
        query = {
            "query":
            f"""
            query {{
                video(id: "{self.video_id}") {{
                    title
                    lengthSeconds
                }}
            }}
            """
        }
        response = requests.post(self.API_URL,
                                 headers=self.headers,
                                 json=query)
        response.raise_for_status()
        data = response.json()
        return data["data"]["video"]

    def get_comments_range(self, start_time, end_time):
        session = requests.Session()
        cursor = None
        comments = []

        def request_payload(cursor=None, start_time=None):
            if cursor:
                return json.dumps([{
                    "operationName": "VideoCommentsByOffsetOrCursor",
                    "variables": {
                        "videoID": self.video_id,
                        "cursor": cursor
                    },
                    "extensions": {
                        "persistedQuery": {
                            "version":
                            1,
                            "sha256Hash":
                            "b70a3591ff0f4e0313d126c6a1502d79a1c02baebb288227c582044aa76adf6a"
                        }
                    }
                }])
            else:
                return json.dumps([{
                    "operationName": "VideoCommentsByOffsetOrCursor",
                    "variables": {
                        "videoID": self.video_id,
                        "contentOffsetSeconds": start_time
                    },
                    "extensions": {
                        "persistedQuery": {
                            "version":
                            1,
                            "sha256Hash":
                            "b70a3591ff0f4e0313d126c6a1502d79a1c02baebb288227c582044aa76adf6a"
                        }
                    }
                }])

        while True:
            payload = request_payload(cursor, start_time)
            response = session.post(self.API_URL,
                                    headers=self.headers,
                                    data=payload)
            response.raise_for_status()
            data = response.json()

            for edge in data[0]['data']['video']['comments']['edges']:
                node = edge['node']
                comment_time = node['contentOffsetSeconds']
                if comment_time >= end_time:
                    return comments
                comments.append({
                    "id":
                    node['id'],
                    "created_at":
                    node['createdAt'],
                    "content_offset_seconds":
                    comment_time,
                    "commenter": {
                        "display_name":
                        node['commenter']['displayName']
                        if node['commenter'] else None,
                        "id":
                        node['commenter']['id'] if node['commenter'] else None,
                        "name":
                        node['commenter']['login']
                        if node['commenter'] else None
                    },
                    "message":
                    node['message']['fragments'][0]['text']
                    if node['message']['fragments'] else ""
                })

            if data[0]['data']['video']['comments']['pageInfo']['hasNextPage']:
                cursor = data[0]['data']['video']['comments']['edges'][-1][
                    'cursor']
            else:
                break

            time.sleep(0.1)

        return comments

    def download_comments(self, progress_callback=None):
        video_info = self.get_video_info()
        length_seconds = video_info["lengthSeconds"]

        chunk_size = length_seconds // self.num_threads
        ranges = [(i * chunk_size, (i + 1) * chunk_size)
                  for i in range(self.num_threads)]
        ranges[-1] = (ranges[-1][0], length_seconds)

        comments = []

        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            futures = {
                executor.submit(self.get_comments_range, start, end):
                (start, end)
                for start, end in ranges
            }
            total_tasks = len(futures)
            completed_tasks = 0

            for future in as_completed(futures):
                comments.extend(future.result())
                completed_tasks += 1
                if progress_callback:
                    progress_callback(completed_tasks / total_tasks * 100)

        comments.sort(key=lambda c: c["content_offset_seconds"])
        return {
            "video": {
                "id": self.video_id,
                "title": video_info["title"],
                "lengthSeconds": length_seconds
            },
            "comments": comments
        }
