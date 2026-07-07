#Import libraries
from xmlrpc import client

import requests as req
import json
from openpyxl import Workbook
import pandas as pd
from apify_client import ApifyClient
from pathlib import Path


def save_data_to_json(results, league, pretty=True, ensure_ascii=False):
    data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    filename = data_dir / f"{league}_raw_data.json"

    with open(filename, "w", encoding="utf-8") as f:
        if pretty:
            json.dump(results, f, ensure_ascii=ensure_ascii, indent=2)
        else:
            json.dump(results, f, ensure_ascii=ensure_ascii, separators=(",", ":"))


def _extract_dataset_id(run):
    """Handles both dict-like and attribute-style Run objects."""
    if isinstance(run, dict):
        return run.get("defaultDatasetId") or run.get("default_dataset_id")
    return getattr(run, "default_dataset_id", None) or getattr(run, "defaultDatasetId", None)


def _extract_status(run):
    if isinstance(run, dict):
        return run.get("status")
    return getattr(run, "status", None)


def pull_data(API_KEY, LEAGUES, INSTA_TEAMS_DICT, LEAGUES_START_DICT):
        client = ApifyClient(API_KEY)

        for league in LEAGUES:
                run_input = {
                        "username": INSTA_TEAMS_DICT[league], 
                        "resultsLimit": 1500,
                        "skipPinnedPosts": True,
                        "onlyPostsNewerThan": LEAGUES_START_DICT[league],
                        "dataDetailLevel": "basicData",
                }

                try:
                        run = client.actor("nH2AHrwxeTRJoN5hX").call(run_input=run_input)
                except Exception as e:
                        print(f"[{league}] actor call raised an exception: {e}")
                        continue

                status = _extract_status(run)
                if status != "SUCCEEDED":
                        print(f"[{league}] WARNING: run status={status} - "
                              f"results may be partial or empty")

                dataset_id = _extract_dataset_id(run)
                if not dataset_id:
                        print(f"[{league}] no dataset id found on run, skipping")
                        continue

                results = list(client.dataset(dataset_id).iterate_items())

                # Tag league on every item for downstream SOV normalization.
                # Print the keys of the first item once to confirm which field
                # ties a post back to its source account (commonly something
                # like "ownerUsername" or "inputUrl" - name varies by actor
                # version), then you can safely remove this print.
                if results:
                        print(f"[{league}] sample item keys: {list(results[0].keys())}")
                for item in results:
                        item["_league"] = league

                save_data_to_json(results, league)

                print(f"Data pulled for {league}: {len(results)} posts "
                      f"across {len(INSTA_TEAMS_DICT[league])} teams.")


def test():
       for league in INSTA_TEAMS_DICT:
                print(INSTA_TEAMS_DICT[league])

       for league in LEAGUES_START_DICT:
                print(LEAGUES_START_DICT[league].to_datetime64())




if __name__ == "__main__":
        API_KEY = "apify_api_7oWYq89jyImoRZaIBxOaSruz27PGdd3Iumkx"

        LEAGUES = ["LigaMX", "LNBP", "CIBACOPA", "LMB", "LMP",
                    "LFA"]

        INSTA_TEAMS_DICT={
            "LigaMX": ["clubamerica", "atlasfc", "atlantefc","cruzazul", "chivas", 
                       "fc_juarez", "clubleon_oficial", "rayados", "clubnecaxa", "tuzosoficial", 
                       "clubpuebla", "clubqueretaro", "clubsantos", "xolos", 
                       "tolucafc", "clubtigres", "pumasmx", "mazatlanfc", "atletidesanluis"],
            "LNBP": ["gambusinosfresnillo.oficial", "clubsoles", "fuerzaregia", "cbsantossanluis",
                     "abejasdeleon", "correbasketuat", "mineroslnbp", "astrosjalisco", "doradosdechihuahuaoficial",
                     "elcalorcancun", "diablosrojosbasquetbol", "lobospueblamx", "freseros_basquetbol",
                     "panterasaguascalientes","halconesrojosmx","halconesdexalapa"],
            "CIBACOPA": ["angelescdmexico", "astrosjalisco", "caballeroscln", "fraylesguasave",
                         "halcones_obregon", "ostionerosgym", "pioneroslm","vamosrayos","toroslagunaoficial",
                         "venadosbasketball", "zonkeysoficial"],
            "LMB": ["acererosoficial", "algodonerosunionlaguna","calientedgo", "charrosbeisbol", "doradoschihlmb",
                    "rielerosags", "clubsaraperos","sultanesoficial","tecolotes_2_laredos",
                    "torosdetijuana", "bravosdeleon", "conspiradoresqro","diablosrojosmx","elaguilabeisbol",
                    "guerrerosoax","leonesdeyucatan", "olmecaastabasco", "pericos_oficial","piratasdecampeche",
                    "tigresqr"],
            "LMP": ["aguilasdemxli", "algodonerosdeguasavemx","verdesxsiempre", "charrosbeisbol", "jaguaresdenayaritoficial_", 
                    "clubtomaterosoficial", "clubnaranjeros", "yaquisoficial", "mayosbeisbol", "venadosbaseball"],
            "LFA": ["caudilloschihuahua", "dinoslfa", "gallosnegroslfa", "mexicas_lfa", "ososlfa", "raptorslfa", "reyes_lfa"]
            }

        #Definition of 2026 beginning dates
        LEAGUES_START_DICT = {
                "LigaMX": "2026-01-09",
                "LNBP": "2025-07-03",
                "CIBACOPA": "2026-02-14",
                "LMB": "2025-04-17",
                "LMP": "2025-10-14",
                "LFA": "2026-04-09"
        }
        
        pull_data(API_KEY, LEAGUES, INSTA_TEAMS_DICT, LEAGUES_START_DICT)