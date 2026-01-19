#!/bin/python
import argparse
import asyncio
from dataclasses import dataclass
import json
import logging
from pathlib import Path
from urllib.parse import urlparse
import aiohttp


parser = argparse.ArgumentParser(description='silly lil updater')
parser.add_argument("-a","--add", type=str,help="Add a mod by providing a project url")
parser.add_argument("-f","--force",default=False,action="store_const",const=True,help="disable mc version check")

args = parser.parse_args()

print(args.force)

logging.basicConfig(level=logging.INFO,format='[%(asctime)s] [%(name)s/%(levelname)s] %(message)s',datefmt='%H:%M:%S')
logger = logging.getLogger("Updater")

minecraft_versions = ["1.21.1"]

async def get_compatible(versions:list,releases_filter=True):
    target_versions = minecraft_versions
    compatible_versions = []
    for v in versions:
        if (any(item in v.get("game_versions") for item in target_versions) or args.force) and "neoforge" in v.get("loaders") and (v.get("version_type") == "release" or not releases_filter) : # prioritize releases
            compatible_versions.append(v)
    return compatible_versions

async def sort_versions(versions: list):
    compatible_versions = await get_compatible(versions)
    if not compatible_versions:
        compatible_versions = await get_compatible(versions,releases_filter=False)
    
    return sorted(compatible_versions, key=lambda x: x['date_published'], reverse=True)


@dataclass
class EnvConfig:
    client: str
    server: str

@dataclass
class hashConfig:
    sha1: str
    sha512: str


async def new(url):
    parsed_url = urlparse(url)
    project_id = parsed_url.path.split("/")[2]
    versions = await sort_versions(await api_request(f"https://api.modrinth.com/v2/project/{project_id}/version"))
    environment = await api_request(f"https://api.modrinth.com/v2/project/{project_id}")
    if not versions:
        return
    new_version = versions[0]
    for f in new_version.get("files"):
        if f.get("primary"):
            return modEntry(
                f.get("url"),
                EnvConfig(
                    environment.get("client_side"),
                    environment.get("server_side")
                ),
                f.get("size"),
                hashConfig(
                    f.get("hashes").get("sha1"),
                    f.get("hashes").get("sha512")
                ),
                f"mods/{f.get("filename")}"
            )

async def api_request(url):
    logger.info(url)
    async with asyncio.Semaphore(10):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        logger.info(f"sucess! {url}")
                        return await response.json()
                    else:
                        logger.warning(f"Failed to fetch versions: {response.status}")
                        return []

            except asyncio.TimeoutError:
                logger.error("Request timed out")
                return []
            except aiohttp.ClientError as e:
                logger.exception(f"HTTP client error: {e}")
                return []
            except Exception as e:
                logger.exception(f"Error fetching versions: {e}")
                return []


@dataclass
class modEntry:
    downloads : str
    env : EnvConfig
    filesize: int
    hashes : hashConfig
    path : str|Path




    async def update(self):
        parsed_url = urlparse(self.downloads)
        project_id = parsed_url.path.split("/")[2]
        versions = await sort_versions(await api_request(f"https://api.modrinth.com/v2/project/{project_id}/version"))
        if not versions:
            return
        new_version = versions[0]
        for f in new_version.get("files"):
            if f.get("primary"):
                self.downloads = f.get("url")
                self.filesize = f.get("size")
                self.hashes.sha1 = f.get("hashes").get("sha1")
                self.hashes.sha512 = f.get("hashes").get("sha512")
                self.path = f"mods/{f.get("filename")}"
                break
    def serilize(self):
        return{
            "downloads": [
                self.downloads
            ],
            "env": {
                "client": self.env.client,
                "server": self.env.server
            },
            "fileSize": self.filesize,
            "hashes": {
                "sha1": self.hashes.sha1,
                "sha512": self.hashes.sha512
            },
            "path": self.path
        }
    
     



async def load_data():
    with open("modrinth.index.json","r") as f:
        return json.load(f)

def convert_files(data):
    mods = []
    for d in data:
        mods.append( 
            modEntry(
                d.get("downloads")[0],
                EnvConfig(
                    d.get("env").get("client"),
                    d.get("env").get("server")
                    ),
                d.get("fileSize"),
                hashConfig(
                    d.get("hashes").get("sha1"),
                    d.get("hashes").get("sha512")
                ),
                d.get("path")
            )
        )
    return mods

async def main():
    data = await load_data()
    mods = convert_files(data.get("files"))
    tasks = []
    for m in mods:
        tasks.append(m.update())
    await asyncio.gather(*tasks)
    new_file_index = []
    for m in mods:
        new_file_index.append(m.serilize())
    data["files"] = new_file_index
    with open("modrinth.index.json","w") as f:
        return json.dump(data,f,indent=2)


async def add_mod(url):
    data = await load_data()
    mod = await new(url)
    data["files"].append(mod.serilize())
    with open("modrinth.index.json","w") as f:
        return json.dump(data,f,indent=2)




if args.add:
    asyncio.run(add_mod(args.add))
else:
    asyncio.run(main())