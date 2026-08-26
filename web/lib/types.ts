/** Shared response shapes used by the pages. */

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface User {
  id: string;
  full_name: string;
  email: string;
  role: "ADMIN" | "OFFICER" | "CASHIER";
}

export interface MemberListItem {
  id: string;
  member_code: string;
  full_name: string;
  phone: string;
  status: "ACTIVE" | "INACTIVE";
  active_loan_code: string | null;
  outstanding: string;
}

export interface LoanListItem {
  id: string;
  loan_code: string;
  member: { id: string; member_code: string; full_name: string };
  principal: string;
  status: "PENDING" | "APPROVED" | "REJECTED" | "DISBURSED" | "CLOSED";
  total_payable: string | null;
  outstanding: string;
  next_due_date: string | null;
}

export interface ScheduleRow {
  seq: number;
  due_date: string;
  principal_due: string;
  interest_due: string;
  amount_due: string;
  principal_paid: string;
  interest_paid: string;
  fee_paid: string;
  status: "PENDING" | "PARTIAL" | "PAID";
  accrued_fee: string;
}

export interface LoanDetail {
  id: string;
  loan_code: string;
  status: LoanListItem["status"];
  member: LoanListItem["member"];
  terms: {
    principal: string;
    interest_rate_annual: string;
    term_count: number;
    frequency: "WEEKLY" | "MONTHLY";
    late_fee: string;
    grace_days: number;
  };
  totals: {
    total_interest: string | null;
    total_payable: string | null;
    installment_amount: string | null;
    paid_total: string;
    outstanding: string;
    accrued_fees: string;
  };
  dates: {
    applied_on: string;
    approved_at: string | null;
    disbursed_on: string | null;
    closed_at: string | null;
  };
  people: { created_by: string; approved_by: string | null; disbursed_by: string | null };
  schedule: ScheduleRow[];
}

export interface PreviewRow {
  seq: number;
  due_date: string;
  principal_due: string;
  interest_due: string;
  amount_due: string;
}

export interface Preview {
  principal: string;
  total_interest: string;
  total_payable: string;
  installment_amount: string;
  schedule: PreviewRow[];
}

export interface Metrics {
  members_total: number;
  loans_active: number;
  disbursed_total: string;
  collected_total: string;
  outstanding_total: string;
}

export interface SettlementQuote {
  as_of: string;
  outstanding: string;
  accrued_fees: string;
  settlement_total: string;
}
