import React, { useMemo, useState } from "react";
import { Chess, Move } from "chess.js";
import { Chessboard } from "react-chessboard";

type AnalyzeResponse = {
  ok: boolean;
  normalized_move: string;
  reaction: string;
  details: Record<string, any>;
};

export default function App() {
  const [fen, setFen] = useState<string>("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  const [gamePly, setGamePly] = useState<number>(0);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<string[]>([]); // SAN list

  const game = useMemo(() => {
    const g = new Chess();
    try {
      g.load(fen);
    } catch {
      g.reset();
      setFen(g.fen());
    }
    return g;
  }, [fen, gamePly]);

  function setStart() {
    const g = new Chess();
    setFen(g.fen());
    setGamePly((n) => n + 1);
    setResult(null);
    setHistory([]);
  }

  function undo() {
    const g = new Chess();
    g.load(fen);
    const m = g.undo();
    if (m) {
      setFen(g.fen());
      setGamePly((n) => n + 1);
      setHistory((h) => h.slice(0, -1));
      setResult(null);
    }
  }

  async function analyzeMoveAndAdvance(move: Move) {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const uci = move.from + move.to + (move.promotion ? move.promotion : "");

      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fen, move: uci })
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail || `HTTP ${res.status}`);
      }
      const data: AnalyzeResponse = await res.json();
      setResult(data);

      // Advance game state and record SAN
      const g = new Chess();
      g.load(fen);
      const made = g.move(move);
      if (made) {
        setFen(g.fen());
        setGamePly((n) => n + 1);
        setHistory((h) => h.concat(g.history({ verbose: false }).slice(-1)));
      }
    } catch (e: any) {
      setError(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  function onPieceDrop(sourceSquare: string, targetSquare: string) {
    const legal = game.moves({ verbose: true }) as Move[];
    let move = legal.find((m) => m.from === sourceSquare && m.to === targetSquare);

    if (!move) {
      // auto-queen promotion attempt
      const maybe = game.move({ from: sourceSquare, to: targetSquare, promotion: "q" as any });
      if (maybe) {
        game.undo();
        move = { from: sourceSquare, to: targetSquare, promotion: "q" } as unknown as Move;
      }
    }

    if (!move) return false;

    analyzeMoveAndAdvance(move);
    return true;
  }

  const engine = result?.details?.engine;
  let evalBox: React.ReactNode = null;
  if (engine?.enabled && engine.before?.ok && engine.after?.ok) {
    const b = engine.before;
    const a = engine.after;
    const bStr = b.score_cp !== null && b.score_cp !== undefined ? (b.score_cp/100).toFixed(2) : (b.mate_in ? `#${b.mate_in}` : "n/a");
    const aStr = a.score_cp !== null && a.score_cp !== undefined ? (a.score_cp/100).toFixed(2) : (a.mate_in ? `#${a.mate_in}` : "n/a");
    evalBox = (
      <p><strong>Engine (d{engine.depth}):</strong> {bStr} → {aStr}, best {a.bestmove || "?"}</p>
    );
  }

  return (
    <div style={{ maxWidth: 1100, margin: "40px auto", fontFamily: "system-ui, Segoe UI, Roboto, Arial" }}>
      <h1>Chess Move Reaction AI</h1>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(320px, 560px) 1fr", gap: 24 }}>
        <div>
          <Chessboard
            position={fen}
            onPieceDrop={onPieceDrop}
            boardWidth={560}
            arePiecesDraggable={!loading}
          />
          <div style={{ marginTop: 12, display: "flex", gap: 8, alignItems: "center" }}>
            <button onClick={setStart} disabled={loading}>Reset</button>
            <button onClick={undo} disabled={loading}>Undo</button>
            <small style={{ opacity: 0.7 }}>FEN:</small>
            <input
              value={fen}
              onChange={(e) => setFen(e.target.value)}
              style={{ flex: 1, minWidth: 0, fontFamily: "monospace", padding: 6 }}
            />
          </div>
          <div style={{ marginTop: 8, fontSize: 12, opacity: 0.75 }}>
            Tip: Drag a piece to make a move. Promotions auto-queen for now.
          </div>
        </div>

        <div>
          <h3>Analysis</h3>
          {loading && <p>Analyzing…</p>}
          {error && <p style={{ color: "#b00020" }}><strong>Error:</strong> {error}</p>}
          {result && (
            <div style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16 }}>
              <p><strong>Move:</strong> {result.normalized_move}</p>
              <p><strong>Reaction:</strong> {result.reaction}</p>
              {evalBox}
              <details>
                <summary>Details</summary>
                <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(result.details, null, 2)}</pre>
              </details>
            </div>
          )}
          {history.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <h4>Moves</h4>
              <p>
                {history.map((m, i) =>
                  i % 2 === 0 ? `${Math.floor(i / 2) + 1}. ${m}` : m
                ).join(" ")}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
