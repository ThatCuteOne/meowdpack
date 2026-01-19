import json
import time


def main():
    MODPACK_VERSION = ""
    with open("pack.json","r") as f:
        data:dict = json.load(f)
        MODPACK_VERSION = data["pack_version"]
    with open("meta.json","r") as pre_write:
        data:dict = json.load(pre_write)
        with open("meta.json","w") as write_file:
            data["versions"].append(
                {
                    "id": MODPACK_VERSION,
                    "releasedAt": int(time.time()),
                    "promotions": {
                        "downloads": {
                            "generic": "https://github.com/ThatCuteOne/meowdpack/releases/latest"
                        }
                    }
                }
            )
            json.dump(data,write_file,indent=2)

main()