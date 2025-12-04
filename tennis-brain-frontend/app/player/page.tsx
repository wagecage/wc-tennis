"use client";
import { useEffect, useState } from "react";
import { Search, TrendingUp, Zap } from "lucide-react";

interface Player {
  name: string;
  elo: number;
  form: number;
  clutch: number;
  surface_hard: number;
  surface_clay: number;
  surface_grass: number;
}

export default function PlayersPage() {
  const [players, setPlayers] = useState<Player[]>([]);
  const [filtered, setFiltered] = useState<Player[]>([]); // Initialize as empty array
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("http://127.0.0.1:8000/players")
      .then((res) => {
        if (!res.ok) {
            throw new Error(`API error: ${res.status}`);
        }
        return res.json();
      })
      .then((data) => {
        // Safety check: Ensure data is actually an array
        if (Array.isArray(data)) {
            setPlayers(data);
            setFiltered(data);
        } else {
            console.error("API returned non-array data:", data);
            setPlayers([]);
            setFiltered([]);
        }
        setLoading(false);
      })
      .catch((err) => {
          console.error("Fetch failed:", err);
          setLoading(false);
          // Optional: set an error state here to show a message to the user
      });
  }, []);

  // Filter logic
  useEffect(() => {
    if (!Array.isArray(players)) return; // Extra safety
    
    const results = players.filter(p => 
      p.name.toLowerCase().includes(search.toLowerCase())
    );
    setFiltered(results);
  }, [search, players]);

  return (
    <main className="animate-fade-in space-y-8">
      {/* HEADER */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Player Database</h1>
          <p className="text-gray-400">Live ratings for {players.length} active players.</p>
        </div>
        
        {/* Search Bar */}
        <div className="relative">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-500" />
          <input 
            type="text" 
            placeholder="Find a player..." 
            className="bg-gray-900 border border-gray-800 rounded-lg pl-10 pr-4 py-2 w-64 text-sm focus:outline-none focus:border-green-500 transition text-white"
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {loading ? (
        <div className="text-center text-gray-500 py-20">Loading Player Data...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Use optional chaining just in case */}
          {filtered?.slice(0, 50).map((player) => (
            <div key={player.name} className="bg-gray-900/50 border border-gray-800 p-5 rounded-xl hover:border-gray-700 transition group">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h3 className="font-bold text-lg text-white group-hover:text-green-400 transition">{player.name}</h3>
                  <div className="text-xs text-gray-500 font-mono">ELO: {player.elo}</div>
                </div>
                <div className="bg-gray-800 p-2 rounded-lg">
                  <TrendingUp className={`w-5 h-5 ${player.form > 0.6 ? "text-green-500" : "text-gray-500"}`} />
                </div>
              </div>

              {/* Stats Grid */}
              <div className="grid grid-cols-3 gap-2 text-xs">
                <StatBox label="Form" value={player.form} />
                <StatBox label="Clutch" value={player.clutch} />
                <StatBox label="Hard" value={player.surface_hard} />
              </div>
            </div>
          ))}
          {/* Show message if no players found */}
          {!loading && filtered.length === 0 && (
              <div className="col-span-full text-center text-gray-500 py-10">
                  No players found.
              </div>
          )}
        </div>
      )}
    </main>
  );
}

function StatBox({ label, value }: { label: string, value: number }) {
  const pct = (value * 100).toFixed(0);
  // Color logic
  let color = "bg-gray-700";
  if (value > 0.65) color = "bg-green-500";
  else if (value > 0.55) color = "bg-green-700";

  return (
    <div className="bg-black/40 rounded p-2 text-center">
      <div className="text-gray-500 mb-1">{label}</div>
      <div className="flex items-center justify-center gap-1">
        <div className="h-1.5 w-full bg-gray-800 rounded-full overflow-hidden">
          <div className={`h-full ${color}`} style={{ width: `${pct}%` }}></div>
        </div>
        <span className="text-gray-300 font-mono">{pct}</span>
      </div>
    </div>
  );
}