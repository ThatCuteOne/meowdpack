import json
import os
import time
import shutil

def main():
    MODPACK_VERSION = ""
    # update meta.json
    with open("pack.json","r") as f:
        data:dict = json.load(f)
        MODPACK_VERSION = data["pack_version"]
    with open("meta.json","r") as pre_write:
        data:dict = json.load(pre_write)
        with open("meta.json","w") as write_file:
            data["versions"].append(
                {
                    "id": MODPACK_VERSION,
                    "releasedAt": int(time.time() * 1000),
                    "promotions": {
                        "downloads": {
                            "generic": "https://github.com/ThatCuteOne/meowdpack/releases/latest"
                        }
                    }
                }
            )
            json.dump(data,write_file,indent=2)
    # move changelog into the right place
    os.makedirs(f"versions/{MODPACK_VERSION}",exist_ok=True)
    shutil.copyfile("changelog.md",f"versions/{MODPACK_VERSION}/changelog.txt")

main()