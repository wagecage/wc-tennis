"use client";
import { useEffect, useState } from "react";

// Define the shape of our Matchup data (must match API)
interface Matchup {
  id: number;
  date: string;
  time: string;
  tournament: string;
  surface: string;
  player_1: string;
  player_2: string;
  model_prob_p1: number;
  model_prob_p2: number;
  odds_p1: number | null;
  odds_p2: number | null;
  value_bet_on: string | null;
  ev: number;
  status: string;
}

export default function Home() {
  const [matchups, setMatchups] = useState<Matchup[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  // Fetch data from Python API on load
  useEffect(() => {
    fetch("http://127.0.0.1:8000/matchups")
      .then((res) => res.json())
      .then((data) => {
        setMatchups(data);
        setLoading(false);
      })
      .catch((err) => console.error("API Error:", err));
  }, []);

  // Group matches by Tournament
  const groupedMatches = matchups.reduce((groups, match) => {
    const key = `${match.tournament} (${match.surface})`;
    if (!groups[key]) groups[key] = [];
    groups[key].push(match);
    return groups;
  }, {} as Record<string, Matchup[]>);

  return (
    <main className="min-h-screen bg-black text-white p-8 font-sans">
      {/* HEADER */}
      <header className="flex justify-between items-center mb-8 border-b border-gray-800 pb-4">
        <h1 className="text-3xl font-bold text-green-500 tracking-tighter">
          TENNIS BRAIN <span className="text-white text-sm font-normal ml-2">BETA</span>
        </h1>
        <div className="flex gap-4">
          <input 
            type="text" 
            placeholder="Search Player..." 
            className="bg-gray-900 border border-gray-700 rounded px-4 py-2 text-sm focus:outline-none focus:border-green-500 transition"
            onChange={(e) => setSearch(e.target.value)}
          />
          <button className="bg-green-600 hover:bg-green-500 text-black font-bold px-6 py-2 rounded transition">
            Subscribe
          </button>
        </div>
      </header>

      {loading ? (
        <div className="text-center text-gray-500 mt-20 animate-pulse">Loading Live Markets...</div>
      ) : (
        <div className="space-y-8">
          {Object.entries(groupedMatches).map(([tournament, matches]) => (
            <div key={tournament} className="animate-fade-in">
              {/* TOURNAMENT HEADER */}
              <div className="flex items-center gap-2 mb-4">
                <div className="h-6 w-1 bg-green-500 rounded-full"></div>
                <h2 className="text-xl font-bold text-gray-200">{tournament}</h2>
              </div>

              {/* MATCH CARDS */}
              <div className="grid gap-3">
                {matches
                  .filter(m => 
                    m.player_1.toLowerCase().includes(search.toLowerCase()) || 
                    m.player_2.toLowerCase().includes(search.toLowerCase())
                  )
                  .map((m) => (
                  <div key={m.id} className="bg-gray-900/50 border border-gray-800 rounded-lg p-4 hover:border-gray-700 transition flex items-center justify-between">
                    
                    {/* Time & Status */}
                    <div className="w-24 text-xs text-gray-500">
                      <div className="font-mono text-gray-300">{m.time}</div>
                      <div>{m.date}</div>
                      {m.status === 'Pending' && <span className="text-yellow-500 animate-pulse">● Live</span>}
                    </div>

                    {/* Players & Probabilities */}
                    <div className="flex-1 grid grid-cols-2 gap-8 px-8">
                      {/* Player 1 */}
                      <div className="relative">
                        <div className="flex justify-between mb-1">
                          <span className={m.value_bet_on === m.player_1 ? "text-green-400 font-bold" : "text-gray-300"}>
                            {m.player_1}
                          </span>
                          <span className="text-xs text-gray-500">{m.odds_p1 ? `@${m.odds_p1.toFixed(2)}` : '-'}</span>
                        </div>
                        {/* Bar */}
                        <div className="h-1.5 w-full bg-gray-800 rounded-full overflow-hidden">
                          <div 
                            className={`h-full ${m.value_bet_on === m.player_1 ? "bg-green-500" : "bg-gray-600"}`} 
                            style={{ width: `${m.model_prob_p1 * 100}%` }}
                          ></div>
                        </div>
                        <div className="text-right text-xs mt-1 text-gray-500">{(m.model_prob_p1 * 100).toFixed(1)}%</div>
                      </div>

                      {/* Player 2 */}
                      <div className="relative">
                        <div className="flex justify-between mb-1">
                          <span className={m.value_bet_on === m.player_2 ? "text-green-400 font-bold" : "text-gray-300"}>
                            {m.player_2}
                          </span>
                          <span className="text-xs text-gray-500">{m.odds_p2 ? `@${m.odds_p2.toFixed(2)}` : '-'}</span>
                        </div>
                        {/* Bar */}
                        <div className="h-1.5 w-full bg-gray-800 rounded-full overflow-hidden">
                          <div 
                            className={`h-full ${m.value_bet_on === m.player_2 ? "bg-green-500" : "bg-gray-600"}`} 
                            style={{ width: `${m.model_prob_p2 * 100}%` }}
                          ></div>
                        </div>
                        <div className="text-right text-xs mt-1 text-gray-500">{(m.model_prob_p2 * 100).toFixed(1)}%</div>
                      </div>
                    </div>

                    {/* Value Badge */}
                    <div className="w-24 flex justify-end">
                      {m.value_bet_on && (
                        <div className="bg-green-500/10 border border-green-500/20 text-green-500 px-3 py-1 rounded text-xs font-bold uppercase tracking-wider">
                          {(m.ev * 100).toFixed(0)}% EV
                        </div>
                      )}
                    </div>

                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}