import React, { useMemo, useState } from "react";
import { Chess, Move, PieceSymbol, Color } from "chess.js";
import { Chessboard } from "react-chessboard";

type AnalyzeResponse = {
  ok: boolean;
  normalized_move: string;
  reaction: string;
  details: Record<string, any>;
};


const PIECES = [
  { type: 'p', color: 'w', symbol: '♙' },
  { type: 'n', color: 'w', symbol: '♘' },
  { type: 'b', color: 'w', symbol: '♗' },
  { type: 'r', color: 'w', symbol: '♖' },
  { type: 'q', color: 'w', symbol: '♕' },
  { type: 'k', color: 'w', symbol: '♔' },
  { type: 'p', color: 'b', symbol: '♟' },
  { type: 'n', color: 'b', symbol: '♞' },
  { type: 'b', color: 'b', symbol: '♝' },
  { type: 'r', color: 'b', symbol: '♜' },
  { type: 'q', color: 'b', symbol: '♛' },
  { type: 'k', color: 'b', symbol: '♚' },
];

function expandFenBoard(fen: string): string[][] {
  const boardPart = fen.split(' ')[0];
  const rows = boardPart.split('/');
  return rows.map(row => {
    let expanded = "";
    for (const char of row) {
      if (/\d/.test(char)) {
        expanded += "1".repeat(parseInt(char));
      } else {
        expanded += char;
      }
    }
    return expanded.split('');
  });
}


function compressBoardToFen(grid: string[][], originalFen: string): string {
  const boardString = grid.map(row => {
    let compressed = "";
    let emptyCount = 0;
    for (const char of row) {
      if (char === '1') {
        emptyCount++;
      } else {
        if (emptyCount > 0) {
          compressed += emptyCount;
          emptyCount = 0;
        }
        compressed += char;
      }
    }
    if (emptyCount > 0) compressed += emptyCount;
    return compressed;
  }).join('/');


  const suffix = originalFen.split(' ').slice(1).join(' ') || "w - - 0 1";
  return `${boardString} ${suffix}`;
}


function manualFenUpdate(currentFen: string, square: string, pieceChar: string | null): string {
  const file = square.charCodeAt(0) - 'a'.charCodeAt(0); // 0-7
  const rank = 8 - parseInt(square[1]); 

  const grid = expandFenBoard(currentFen);
  

  grid[rank][file] = pieceChar || '1';

  return compressBoardToFen(grid, currentFen);
}


function manualFenMove(currentFen: string, source: string, target: string): string {
  const srcFile = source.charCodeAt(0) - 'a'.charCodeAt(0);
  const srcRank = 8 - parseInt(source[1]);
  const tgtFile = target.charCodeAt(0) - 'a'.charCodeAt(0);
  const tgtRank = 8 - parseInt(target[1]);

  const grid = expandFenBoard(currentFen);
  
  const piece = grid[srcRank][srcFile];
  if (piece === '1') return currentFen; 

  grid[srcRank][srcFile] = '1'; 
  grid[tgtRank][tgtFile] = piece; 

  return compressBoardToFen(grid, currentFen);
}


export default function App() {
  // Game
  const [fen, setFen] = useState<string>("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  const [isSetupMode, setIsSetupMode] = useState(false);
  const [selectedPiece, setSelectedPiece] = useState<{type: string, color: string} | null>(null);

  // Analysis 
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<string[]>([]);

  // Validation 
  const isValidFen = useMemo(() => {
    try {
      const c = new Chess();
      c.load(fen);
      return true;
    } catch {
      return false;
    }
  }, [fen]);

  const game = useMemo(() => {
    const g = new Chess();
    try { g.load(fen); } catch { }
    return g;
  }, [fen]);

  function handleReset() {
    setFen("rnbqkbnr/pppppppp/8/8/8/4P3/PPPP1PPP/RNBQKBNR w KQkq - 0 1"); // Default start
    setResult(null);
    setHistory([]);
    setError(null);
    setIsSetupMode(false);
  }


  async function analyzeMove(move: Move) {
    setLoading(true);
    setError(null);
    try {
      const uci = move.from + move.to + (move.promotion || "");
      const res = await fetch("http://127.0.0.1:8000/api/analyze", {
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
      
 
      const g = new Chess(fen);
      g.move(move);
      setFen(g.fen());
      setHistory(prev => [...prev, g.history().pop()!]);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }



  function onDrop(source: string, target: string) {

    if (isSetupMode) {
        const newFen = manualFenMove(fen, source, target);
        setFen(newFen);
        return true;
    }

    const moves = game.moves({ verbose: true }) as Move[];
    let move = moves.find(m => m.from === source && m.to === target);


    if (!move) {
      const promoMove = game.move({ from: source, to: target, promotion: 'q' });
      if (promoMove) {
        game.undo(); 
        move = { from: source, to: target, promotion: 'q' } as Move;
      }
    }

    if (move) {
      analyzeMove(move);
      return true;
    }
    return false;
  }


  function onSquareClick(square: string) {
    if (!isSetupMode || !selectedPiece) return;


    const char = selectedPiece.color === 'w' 
      ? selectedPiece.type.toUpperCase() 
      : selectedPiece.type.toLowerCase();

    const newFen = manualFenUpdate(fen, square, char);
    setFen(newFen);
  }


  function onSquareRightClick(square: string) {
    if (!isSetupMode) return;
    const newFen = manualFenUpdate(fen, square, null); 
    setFen(newFen);
  }

  return (
    <div className="container">
      <h1>Chess Move Reaction AI</h1>

      <div className="grid-layout">
        {/* Board */}
        <div>
          {isSetupMode && (
            <div className="setup-tools">
              <div className="instruction-text">
                Select a piece below and <strong>Left-Click</strong> board to place.<br/>
                <strong>Right-Click</strong> any square to remove a piece.
              </div>
              <div className="piece-palette">
                {PIECES.map((p) => (
                  <div
                    key={p.color + p.type}
                    className={`palette-piece ${selectedPiece?.type === p.type && selectedPiece?.color === p.color ? 'selected' : ''}`}
                    onClick={() => setSelectedPiece({type: p.type, color: p.color})}
                  >
                    {p.symbol}
                  </div>
                ))}
              </div>
            </div>
          )}

          <Chessboard 
            position={fen} 
            onPieceDrop={onDrop}
            onSquareClick={onSquareClick}
            onSquareRightClick={onSquareRightClick}
            boardWidth={560}
            arePiecesDraggable={!loading}
            animationDuration={200}
            customDarkSquareStyle={{ backgroundColor: "#779954" }}
            customLightSquareStyle={{ backgroundColor: "#e9edcc" }}
          />

          <div className="controls">
            <div style={{display: 'flex', justifyContent: 'space-between', marginBottom: 10}}>
              <div style={{display:'flex', gap: 10}}>
                <button className="btn secondary" onClick={handleReset}>Reset Board</button>
                <button 
                  className={`btn ${isSetupMode ? "secondary" : ""}`}
                  onClick={() => setIsSetupMode(!isSetupMode)}
                >
                  {isSetupMode ? "Done Setup" : "Setup Board"}
                </button>
              </div>
              {isSetupMode && (
                <button className="btn secondary" onClick={() => setFen("8/8/8/8/8/8/8/8 w - - 0 1")}>
                  Clear Board
                </button>
              )}
            </div>

            <div className="fen-input-group">
              <span style={{color: '#888', fontSize: '0.9rem'}}>FEN:</span>
              <input 
                className={`fen-input ${!isValidFen ? 'invalid' : ''}`}
                value={fen}
                onChange={(e) => setFen(e.target.value)}
              />
            </div>
            {!isValidFen && <small style={{color: 'var(--danger-color)'}}>Invalid FEN Position (Game Logic Disabled)</small>}
          </div>
        </div>

        {/* Analysis */}
        <div className="analysis-panel">
          {error && (
            <div className="card" style={{borderLeft: '4px solid var(--danger-color)'}}>
              <strong>Error:</strong> {error}
            </div>
          )}
          
          {loading && <div className="card">Analyzing move...</div>}

          {!loading && result && (
            <div className="card">
              <div className="reaction-box">
                <p className="reaction-text">{result.reaction}</p>
                <small style={{color: '#888'}}>{result.normalized_move}</small>
              </div>

              {result.details?.engine?.enabled && result.details.engine_summary?.available && (
                <div className="eval-bar">
                  <span>
                    Eval: <strong>{result.details.engine_summary.after_cp / 100}</strong>
                  </span>
                  <span>
                    Delta: <strong style={{
                      color: result.details.engine_summary.delta_cp > 0 ? 'var(--success-color)' : 'var(--danger-color)'
                    }}>
                      {result.details.engine_summary.delta_cp > 0 ? "+" : ""}
                      {result.details.engine_summary.delta_cp / 100}
                    </strong>
                  </span>
                </div>
              )}
              
              <div style={{marginTop: 20}}>
                <details>
                  <summary className="details-summary">View Raw Details</summary>
                  <pre style={{fontSize: '0.8rem', color: '#888', overflowX: 'auto'}}>
                    {JSON.stringify(result.details, null, 2)}
                  </pre>
                </details>
              </div>
            </div>
          )}

          <div className="card">
            <h3 style={{marginTop: 0, fontSize: '1rem'}}>Move History</h3>
            <div className="history-list">
              {history.length === 0 ? "No moves yet." : history.map((m, i) => (
                <span key={i} style={{marginRight: 10}}>
                  {i % 2 === 0 ? `${Math.floor(i/2) + 1}.` : ""} <span style={{color: 'white'}}>{m}</span>
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}