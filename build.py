#!/bin/python
import json
import os
import zipfile
import shutil

# load pack data
with open('pack.json') as f:
    config = json.load(f)
    PACK_VERSION = config.get('pack_version')
    MINECRAFT_VERSION = config.get('mc_version')
    LOADER_VERSION = config.get('neoforge_version')
    VERSION_ID = f"{PACK_VERSION}-mc{MINECRAFT_VERSION}"

def setup_build_env():
    # Remove existing file if it exists
    if os.path.exists("pack-dev-build.mrpack"):
        os.remove("pack-dev-build.mrpack")
    if os.path.exists("./.build"):
        shutil.rmtree("./.build")
    os.mkdir('.build')
    shutil.copytree('./overrides', './.build/overrides')
    shutil.copy('modrinth.index.json','./.build/')
    os.chdir("./.build")


def build():
    # set index data from pack.json
    with open('modrinth.index.json') as f:
        index = json.load(f)
        index['dependencies']['minecraft'] = MINECRAFT_VERSION
        index['dependencies']['neoforge'] = LOADER_VERSION
        index['versionId'] = VERSION_ID
        index['name'] = f"Adaptive {VERSION_ID}"
        with open('modrinth.index.json','w') as f:
            json.dump(index,f,indent=4)
    # set Mod updater config data from pack.json
    with open('overrides/config/modpack-update-checker/config.json') as f:
        data = json.load(f)
        data['currentVersion'] = VERSION_ID
        data['display_version'] = f"v{PACK_VERSION}"
        with open('overrides/config/modpack-update-checker/config.json','w') as f:
            json.dump(data,f,indent=4)
    

    # Create new zip file
    with zipfile.ZipFile("../pack-dev-build.mrpack", "w", zipfile.ZIP_DEFLATED) as zipf:
        # Add overrides directory
        for root, dirs, files in os.walk("./overrides"):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, start=".")
                zipf.write(file_path, arcname)
        
        # Add modrinth.index.json
        if os.path.exists("modrinth.index.json"):
            zipf.write("modrinth.index.json", "modrinth.index.json")

if __name__ == "__main__":
    setup_build_env()
    build()
