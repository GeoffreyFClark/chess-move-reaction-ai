import argparse
from explain import explain_move

def main():
    p = argparse.ArgumentParser(description="Chess Move Reaction AI (CLI)")
    p.add_argument("--fen", required=True, help="FEN string")
    p.add_argument("--move", required=True, help="Move in SAN (e.g., Nf3) or UCI (e.g., g1f3)")
    args = p.parse_args()

    result = explain_move(args.fen, args.move)
    print(f"Move: {result['normalized_move']}")
    print(f"Reaction: {result['reaction']}")
    print("Details:")
    for k, v in result["details"].items():
        if k == "engine" and isinstance(v, dict) and v.get("enabled"):
            print("  - engine: enabled")
            before = v.get("before", {})
            after = v.get("after", {})
            print(f"    - depth: {v.get('depth')}")
            print(f"    - before: centipawn={before.get('score_centipawn')} mate={before.get('mate_in')} best={before.get('bestmove')}")
            print(f"    - after:  centipawn={after.get('score_centipawn')} mate={after.get('mate_in')} best={after.get('bestmove')}")
        else:
            print(f"  - {k}: {v}")

if __name__ == "__main__":
    main()
