from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main():
    sc = OAuth2(None, None, from_file=str(PROJECT_ROOT / "backend" / "oauth2.json"))
    gm = yfa.Game(sc, "nhl")
    print("your available NHL league keys:")
    print(gm.league_ids())


if __name__ == "__main__":
    main()
