import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Link from "next/link";
import { Activity, Trophy, Users, Zap } from "lucide-react"; // Import Icons

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "WC Tennis | Predictive Analytics",
  description: "Wage Cage Tennis: Professional predictive engine.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-black text-gray-100`}>
        {/* --- NAVIGATION BAR --- */}
        <nav className="border-b border-gray-800 bg-gray-950/50 backdrop-blur-md sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
            {/* Logo */}
            <div className="flex items-center gap-2">
              <Zap className="text-green-500 w-6 h-6" />
              <span className="text-xl font-bold bg-gradient-to-r from-green-400 to-emerald-600 bg-clip-text text-transparent">
                WAGE CAGE TENNIS
              </span>
            </div>

            {/* Links */}
            <div className="flex gap-8 text-sm font-medium text-gray-400">
              <Link href="/" className="hover:text-green-400 transition flex items-center gap-2">
                <Activity className="w-4 h-4" />
                LIVE BOARD
              </Link>
              <Link href="/results" className="hover:text-green-400 transition flex items-center gap-2">
                <Trophy className="w-4 h-4" />
                RESULTS
              </Link>
              <Link href="/player" className="hover:text-green-400 transition flex items-center gap-2">
                <Users className="w-4 h-4" />
                PLAYERS
              </Link>
            </div>

            {/* Auth / Subscribe */}
            <div>
              <button className="bg-white text-black px-4 py-1.5 rounded-full text-sm font-bold hover:bg-gray-200 transition">
                Sign In
              </button>
            </div>
          </div>
        </nav>

        {/* --- MAIN CONTENT --- */}
        <div className="max-w-7xl mx-auto p-6">
          {children}
        </div>
      </body>
    </html>
  );
}