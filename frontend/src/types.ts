export type Status = 'act' | 'watch' | 'steady' | 'not_held'
export type Component = 'RBC' | 'FFP' | 'PLT'

export interface ModeInfo {
  mode: 'model' | 'fallback'
  model: string
  mode_note: string
  fallback_forced: boolean
  model_available: boolean
}

export interface Facility {
  facility_id: string
  name: string
  facility_type: string
  county: string
  region_name: string
  connectivity: string
}

export interface User {
  username: string
  display_name: string
  role: 'hospital_officer' | 'regional_officer'
  role_label: string
  facility_id: string
  facility_name: string
  facilities: Facility[]
}

export interface DemoUser {
  username: string
  display_name: string
  role: string
  role_label: string
  facility_name: string
  demo_password: string
}

export interface Reason {
  icon: string
  text: string
}

export interface SuggestionPart {
  label: string
  units: number
}

export interface Suggestion {
  kind: 'order' | 'early_delivery' | 'drive'
  unit_word?: string
  title: string
  needs_approval: string | null
  quantity: number
  usual_quantity: number
  for_date: string
  for_label: string
  capped?: boolean
  parts: SuggestionPart[]
  sum_text: string
}

export interface Decision {
  decision_id: number
  created_at: string
  username: string
  display_name: string
  role: string
  as_of: string
  series_id: string
  facility_id: string
  facility_name?: string
  component: Component
  blood_group: string
  blood_group_label: string
  suggestion_kind: string
  for_date: string | null
  status_seen: Status
  suggested_quantity: number
  action: 'accept' | 'change' | 'reject'
  final_quantity: number
  reason_code: string | null
  reason_label?: string | null
  note: string | null
  mode: string
  summary: string
  at_label: string
  withdrawn?: boolean
  withdrawn_at?: string | null
}

export interface ProjectionDay {
  date: string
  label: string
  weekend: boolean
  demand: number
  demand_low: number
  demand_high: number
  delivery: number
  is_delivery_day: boolean
  expiring: number
  stock: number
  stock_low: number
  stock_high: number
  short: number
}

export interface Series {
  id: string
  facility_id: string
  facility_name: string
  component: Component
  component_label: string
  blood_group: string
  blood_group_label: string
  blood_group_words: string
  as_of: string
  model: string
  mode: string
  held: boolean
  status: Status
  status_label: string
  status_line: string
  status_why?: string
  units_on_shelf: number
  shelf_split?: Record<string, number>
  expected_use_7_days: number
  expected_use_7_days_range: [number, number]
  expected_daily_use?: number
  cover_days: number | null
  cover_capped?: boolean
  worst_cover_days?: number | null
  next_delivery?: { date: string; label: string; days_away: number; usual_units: number } | null
  arriving_today?: number
  stockout_date?: string | null
  worst_stockout_date?: string | null
  shortfall_before_delivery?: number
  expiring_before_delivery?: number
  minimum_stock?: number
  emergency_lead_hours?: number
  deliveries_from_supply_forecast?: boolean
  suggestion: Suggestion | null
  reasons: Reason[]
  decision?: Decision | null
  projection?: ProjectionDay[]
  compatible_cover?: {
    units: number
    groups: { blood_group: string; blood_group_label: string; units: number }[]
    note: string
  } | null
  actual?: {
    note: string
    summary: string
    days: { date: string; label: string; requested: number; requests_not_fully_met: number; shortage_requests: number; stock: number }[]
  }
  forecast_compare?: { baseline_7_days: number; model_7_days: number | null }
  facility?: Facility
  action_label?: string
}

export interface Brief extends ModeInfo {
  as_of: string
  as_of_label: string
  facility: Facility
  component: Component
  component_label: string
  components: { component: Component; label: string; held: boolean }[]
  sentence: string
  sms_preview: string | null
  next_delivery_label: string | null
  counts: Record<Status, number>
  series: Series[]
}

export interface AsOfDates {
  default: string
  dates: { date: string; label: string; note: string }[]
}

export interface ReasonCodes {
  change: { code: string; label: string }[]
  reject: { code: string; label: string }[]
}

export interface RegionWeek {
  week: number
  start: string
  label: string
  short_label: string
  school_break: boolean
  expected_cleared: number
  usual_cleared: number
  demand: number
  units_short: number
  scheduled_drives: number
  expected_donors: number
}

export interface DriveSuggestion {
  id: string
  as_of: string
  week: number
  week_label: string
  school_break: boolean
  groups_short: string[]
  text: string
  venue_text: string
  suggestion: Suggestion
  decision?: Decision | null
  action_label?: string
}

export interface RegionView extends ModeInfo {
  as_of: string
  centre: { facility_id: string; name: string; region_name: string }
  weeks: RegionWeek[]
  groups: {
    blood_group: string
    blood_group_label: string
    stock_now: number
    weeks: { week: number; demand: number; cleared: number; short: number; stock_end: number }[]
  }[]
  drive_suggestions: DriveSuggestion[]
  supply_change_pct: number
  rates: { units_per_donation: number; median_testing_wait_days: number }
  what_if: { date: string; donors: number }[]
  notes: string[]
}

export interface Overview extends ModeInfo {
  as_of: string
  facilities: (Facility & {
    act: number
    watch: number
    next_delivery_label: string | null
    groups: { id: string; blood_group: string; blood_group_label: string; status: Status; status_label: string; cover_days: number | null; cover_capped: boolean; units_on_shelf: number }[]
  })[]
}
