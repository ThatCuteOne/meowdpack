#!/bin/python
import argparse
import asyncio
from dataclasses import dataclass
import json
import logging
from pathlib import Path
from urllib.parse import urlparse
import aiohttp


parser = argparse.ArgumentParser(description="silly lil updater")
parser.add_argument("-a","--add", type=str,help="Add a mod by providing a project url")
parser.add_argument("-f","--force",default=False,action="store_const",const=True,help="disable mc version check")
parser.add_argument("-c","--changelog",default=False,action="store_const",const=True,help="Generate modlist")

LOADER = "neoforge"
MINECRAFT_VERSIONS = ["1.21.1"]
MINECRAFT_VERSIONS.reverse()
args = parser.parse_args()

logging.basicConfig(level=logging.INFO,format="[%(asctime)s] [%(name)s/%(levelname)s] %(message)s",datefmt="%H:%M:%S")
logger = logging.getLogger("Updater")


async def get_compatible(versions: list, releases_filter=True):
    target_versions = MINECRAFT_VERSIONS
    compatible_versions = []
    for v in versions:
        version_supported = any(
                item in v.get("game_versions") 
                for item in target_versions
            ) or args.force
        
        loader_supported = LOADER in v.get("loaders")

        release_type_ok = v.get("version_type") == "release" or not releases_filter

        if version_supported and loader_supported and release_type_ok:
            compatible_versions.append(v)
    return compatible_versions

async def sort_versions(versions: list):
    compatible_versions = await get_compatible(versions, releases_filter=False)
    # if not compatible_versions:
    #     compatible_versions = await get_compatible(versions, releases_filter=False)
    
    return sorted(compatible_versions, key=lambda x: x["date_published"], reverse=True)


@dataclass
class EnvConfig:
    client: str
    server: str


@dataclass
class hashConfig:
    sha1: str
    sha512: str


@dataclass
class modConfig:
    title: str
    modrinth_id: str
    version_identifier: str



async def new(url):
    parsed_url = urlparse(url)
    project_id = parsed_url.path.split("/")[2]
    versions = await sort_versions(await api_request(
        f"https://api.modrinth.com/v2/project/{project_id}/version"
        )
    )
    environment = await api_request(
        f"https://api.modrinth.com/v2/project/{project_id}"
    )
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
    logger.info(f"Requesting:{url}")

    async with asyncio.Semaphore(10):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        logger.info(f"Success! {url}")
                        text = await response.text()
                        try:
                            return json.loads(text)
                        except json.JSONDecodeError:
                            return await response.json()
                    else:
                        logger.warning(
                            f"Failed to fetch: {response.status}"
                        )
                        return  {}

            except asyncio.TimeoutError:
                logger.error("Request timed out")
                return {}
            except aiohttp.ClientError as e:
                logger.exception(f"HTTP client error: {e}")
                return {}
            except Exception as e:
                logger.exception(f"Error fetching: {e}")
                return {}

async def get_modpack_version():
    with open("pack.json","r") as f:
        filejson:dict = json.load(f)
        f.close()
        return f"{filejson.get("adaptive_version")}-mc{filejson.get("mc_version")}"


@dataclass
class changeLog:
    updated_mods = []
    new_mods = []
    removed_mods = []

    async def get_dev_notes(self):
        with open("changelog_comment.md","r") as f:
            return f.read()

    

    async def write_to_file(self):

        dev_notes = await self.get_dev_notes()
        modpack_version = await get_modpack_version()

        with open("changelog.md", "w") as changelogfile:
            parts = []

            parts.append(f"# Adaptive {modpack_version}\n")

            if dev_notes:
                parts.append("### Dev Notes\n")
                parts.append(dev_notes)

            if self.new_mods:
                parts.append("\n### New Mods! \n")
                for new_mod in self.new_mods:
                    if new_mod is not None:
                        parts.append(f"- ➕️ {new_mod.get("title")}\n")
            
            if self.removed_mods:
                parts.append("\n### Removed Mods 🗑️\n")
                for removed_mod in self.removed_mods:
                    if removed_mod is not None:
                        parts.append(f"- 🗑️ {removed_mod.get("title")}\n")
            
            if self.updated_mods:
                parts.append("\n### Updated Mods 🔺\n")
                for updated_mod in self.updated_mods:
                    if updated_mod is not None:
                        parts.append(
                            f"- 🔺{updated_mod.get("title")}: "
                            f"{updated_mod.get("old_version")} **»»»** "
                            f"{updated_mod.get("new_version")}\n"
                        )

            new_data = "".join(parts)
            changelogfile.write(new_data)
            changelogfile.close()


@dataclass
class modEntry:
    downloads : str
    env : EnvConfig
    filesize: int
    hashes : hashConfig
    path : str|Path
    mod_data : modConfig = None


    async def get_modrinth_id(self) -> str:
        parsed_url = urlparse(self.downloads)
        return parsed_url.path.split("/")[2]
    async def get_version_id(self) -> str:
        parsed_url = urlparse(self.downloads)
        return parsed_url.path.split("/")[4]


    async def get_project_data(self):
        if self.mod_data is not None:
            return self.mod_data
        project_id = await self.get_modrinth_id()
        version_id = await self.get_version_id()
        data:dict = await api_request(f"https://api.modrinth.com/v2/project/{project_id}")
        version:dict = await api_request(f"https://api.modrinth.com/v2/project/{project_id}/version/{version_id}")
        self.mod_data = modConfig(
            title=data.get("title"),
            modrinth_id=project_id,
            version_identifier=version.get("version_number")
        )


    async def update(self):
        project_id = await self.get_modrinth_id()
        versions = await sort_versions(await api_request(f"https://api.modrinth.com/v2/project/{project_id}/version"))
        if not versions:
            return
        new_version = versions[0]
        for f in new_version.get("files"):
            if f.get("primary"):
                if self.hashes.sha1 == f.get("hashes").get("sha1") and self.hashes.sha512 == f.get("hashes").get("sha512"): 
                    return
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
    mods: list[modEntry] = convert_files(data.get("files"))
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

async def generate_changelog():
    async def is_same_mod(mod_a: modEntry, mod_b: modEntry) -> bool:
        if await mod_a.get_modrinth_id() == await mod_b.get_modrinth_id():
            return True
        return False

    async def search_mods(new_mod: modEntry, old_mods: list[modEntry], changelog: changeLog, matched_old_mods: list):
        for old_mod in old_mods:
            if await is_same_mod(new_mod,old_mod):
                matched_old_mods.append(old_mod)
                if await new_mod.get_version_id() == await old_mod.get_version_id():
                    return # if this is true it means its 100% the same modversion
                await asyncio.gather(
                        new_mod.get_project_data(),
                        old_mod.get_project_data()
                        )
                changeLog.updated_mods.append({
                    "title": new_mod.mod_data.title,
                    "new_version": new_mod.mod_data.version_identifier,
                    "old_version": old_mod.mod_data.version_identifier
                })
                return
        await new_mod.get_project_data()
        changelog.new_mods.append(
            {
                "title": new_mod.mod_data.title
            }
        )
    async def get_latest_tag() -> str:
        github_data: dict = await api_request(
            "https://api.github.com/repos/thatcuteone/adaptive/releases/latest"
            )
        if not github_data: 
            return
        return github_data.get("tag_name")

    async def get_old_mods() -> list[modEntry]:
        git_tag = await get_latest_tag()
        mod_data = await api_request(
            f"https://raw.githubusercontent.com/ThatCuteOne/adaptive/refs/tags/{git_tag}/modrinth.index.json"
            )
        return convert_files(mod_data.get("files"))

    async def removed_mods(old_mod: modEntry,changelog: changeLog):
        await old_mod.get_project_data()
        changelog.removed_mods.append({
            "title": old_mod.mod_data.title
        })
    
    changelog = changeLog()

    data = await load_data()
    current_mods: list[modEntry] = convert_files(data.get("files"))
    old_mods = await get_old_mods()

    matched_old_mods = []

    tasks = []
    for new_mod in current_mods:
        tasks.append(search_mods(new_mod, old_mods, changelog, matched_old_mods))

    await asyncio.gather(*tasks)
    removed_mods_tasks = []
    for old_mod in old_mods:
        if old_mod not in matched_old_mods:
            removed_mods_tasks.append(removed_mods(old_mod,changelog))

    await asyncio.gather(*removed_mods_tasks)
    await changelog.write_to_file()


if __name__ == "__main__":
    if args.add:
        asyncio.run(add_mod(args.add))
    elif args.changelog:
        asyncio.run(generate_changelog())
    else:
        asyncio.run(main())