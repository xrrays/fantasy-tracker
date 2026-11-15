export type Team = {
  key: string; name: string; manager: string; rank: number | null; division: string;
  wins: number | null; losses: number | null; ties: number | null; win_pct: number | null;
  pf: number | null; pa: number | null; moves: number | null; trades: number | null;
  all_wins: number; all_losses: number; all_ties: number; expected_wins: number | null;
  completed_weeks: number; average: number | null; schedule_strength: number | null;
  margin: number | null; consistency: number | null;
}
export type Matchup = { week: number; status: string; start: string; end: string; playoffs: boolean; consolation: boolean;
  teams: { key: string; name: string; points: number | null }[] }
export type Player = { key: string; name: string; nhl_team: string; positions: string[]; group: string;
  image: string; image_fallback?: string; status: string; status_code?: string; points: number | null; stats: Record<string, number | null>; rank: number | null }
export type DraftPick = { player: string; team: string; pick: number | null; round: number | null }
export type Move = { id: string; type: string; timestamp: string; players: {
  player: string; name: string; action: string; source_type: string; source: string | null; destination: string | null
}[] }
export type RosterGroup = { count: number; covered: number; points: number | null; average_points: number | null; stats: Record<string,number|null>; average_pos_rank: number | null; top100: number; rank: number | null; total_rank: number | null }
export type RosterProfile = RosterGroup & { key: string; name: string; manager: string; status_flags: number;
  groups: Record<string,RosterGroup>; player_ranks: Record<string,{rank:number|null;pos_rank:number|null}> }
export type TradeProduction = { points: number | null; complete: boolean; covered: number; expected: number; start: string; end: string;
  players?: Record<string,{points:number|null;complete:boolean;covered:number;expected:number}> }
export type Recent = { points: Record<string, number | null>; stats?: Record<string, Record<string, number | null>>; start: string; end: string; pool_size: number; fetched_at: string; complete?: boolean; paused?: boolean }
export type Pickup = { id: string; player: string; name: string; team: string; source: string;
  start: string; end: string; points: number | null; days: number; covered_days: number; active?: boolean; points_complete?: boolean; paused?: boolean }
export type DrakeEdition = { league_key: string; season: string; through_week: number; published_at: string; source_updated_at: string;
  entries: { team_key: string; rank: number; name?: string; blurb: string }[] }
export type Dashboard = {
  preview?: boolean;
  favorite_team_key?: string | null;
  jordog_editions?: Record<string,string[]>;
  league: { name: string; season: string; week: number; key: string };
  teams: Team[]; matchups: Matchup[]; players: Player[]; draft: DraftPick[]; transactions: Move[];
  daily: { date: string; scores: Record<string, number | null> }[];
  daily_by_week?: Record<string, { date: string; scores: Record<string, number | null> }[]>;
  pickups?: Pickup[]; pickups_loaded?: boolean; transactions_complete?: boolean;
  roster_owners?: Record<string, string>; rosters_loaded?: boolean;
  roster_profiles?: Record<string,RosterProfile[]>;
  credited?: { profiles: Record<string,RosterProfile[]>; coverage: Record<string,{start:string;end:string;complete:boolean;covered:number;expected:number}>;
    reconciliation: {checked:number;matched:number;daily_checked?:number;daily_matched?:number;differences?:{week:number;team:string;calculated:number;official:number}[]} };
  trade_production?: Record<string,Record<string,TradeProduction>>;
  drake_editions?: DrakeEdition[];
  records: { highest: { team: string; points: number; week: number } | null;
    closest: { teams: string[]; margin: number; week: number } | null;
    comeback?: { team: string; opponent: string; week: number; deficit: number; date: string } | null; comeback_covered?: number };
  recent: Record<string, Recent>; recent_pool?: string[]; stat_labels: Record<string, string>;
  players_loaded: boolean; managers_loaded: boolean; updated_at: string; coverage: string[];
}
export type Snapshot = { data: Dashboard | null; running: boolean; message: string; error: string | null; requests: number; budget: number; refresh_due?: boolean }
