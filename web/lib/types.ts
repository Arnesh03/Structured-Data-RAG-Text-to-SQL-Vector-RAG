export type Route = "sql" | "rag";

export interface Health {
  ok: boolean;
  llm_provider: string;
  llm_model: string;
  has_api_key: boolean;
  database_ready: boolean;
  vectorstore_ready: boolean;
}

export interface ExampleQuestion {
  q: string;
  route: Route;
}

export interface SourceRef {
  file: string;
  title: string;
}

export interface Chunk extends SourceRef {
  page: number | null;
  text: string;
}

export interface Kpis {
  total_admissions: number;
  unique_patients: number;
  hospitals: number;
  doctors: number;
  total_billing: number;
  avg_billing: number;
  avg_stay_days: number;
  avg_age: number;
  first_admission: string;
  last_admission: string;
  emergency_share: number;
  abnormal_share: number;
}

export interface Series {
  name: string;
  admissions: number;
  [key: string]: string | number;
}

export interface Dashboard {
  kpis: Kpis;
  by_condition: Series[];
  by_month: Series[];
  by_admission_type: Series[];
  by_insurance: Series[];
  by_age_group: Series[];
  by_test_result: Series[];
  by_gender: Series[];
  by_medication: Series[];
  stay_by_condition: Series[];
  top_hospitals: Series[];
}

export interface SchemaColumn {
  name: string;
  type: string;
  description: string;
}

export interface PreprocessingStep {
  step: string;
  detail: string;
  rows_dropped?: number;
  values_changed?: number;
  columns_added?: number;
  unique_patients?: number;
  unexpected_values?: Record<string, string[]>;
}

export interface PreprocessingReport {
  generated_at: string;
  rows_in: number;
  rows_out: number;
  rows_dropped: number;
  columns_out: string[];
  steps: PreprocessingStep[];
  summary: {
    unique_patients: number;
    unique_hospitals: number;
    unique_doctors: number;
    date_range: [string, string];
    total_billing: number;
    median_stay_days: number;
  };
}

export interface PolicyDocument {
  file: string;
  title: string;
  sections: string[];
}

/** One stage of the pipeline, as reported by the SSE stream. */
export type Stage =
  | "routing"
  | "generating_sql"
  | "executing_sql"
  | "retrieving"
  | "answering";

export type StreamEvent =
  | { type: "stage"; stage: Stage }
  | { type: "route"; route: Route; label: string; elapsed: number }
  | { type: "sql"; sql_query: string }
  | { type: "rows"; columns: string[]; rows: (string | number | null)[][]; row_count: number }
  | { type: "sources"; sources: SourceRef[]; chunks: Chunk[] }
  | { type: "token"; text: string }
  | { type: "done"; result: AskResult }
  | { type: "error"; message: string };

export interface AskResult {
  question: string;
  route: Route | null;
  answer: string;
  ok: boolean;
  elapsed: number;
  sql_query?: string;
  columns?: string[];
  rows?: (string | number | null)[][];
  row_count?: number;
  sources?: SourceRef[];
  chunks?: Chunk[];
}

/** A chat turn, built up incrementally as stream events arrive. */
export interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  route?: Route;
  stage?: Stage;
  done?: boolean;
  error?: string;
  elapsed?: number;
  sql?: string;
  columns?: string[];
  rows?: (string | number | null)[][];
  rowCount?: number;
  sources?: SourceRef[];
  chunks?: Chunk[];
}
