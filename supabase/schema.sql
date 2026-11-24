-- NovaOS Updates Schema (Supabase / PostgreSQL)
-- شغّل هذا الملف في SQL editor في مشروع Supabase الخاص بك.

create table if not exists public.updates (
  id uuid primary key default gen_random_uuid(),
  version text not null,
  channel text not null default 'stable' check (channel in ('stable', 'beta', 'nightly')),
  release_url text not null,          -- رابط GitHub Release (الأصول: .deb + .sig/.minisig)
  sha256 text not null,
  notes text,
  created_at timestamptz not null default now()
);

-- فهرس يسرّع "أحدث نسخة لكل قناة"
create index if not exists idx_updates_channel_created_at
  on public.updates (channel, created_at desc);

-- تفعيل Row Level Security
alter table public.updates enable row level security;

-- سياسة القراءة: عامة لأي شخص (anon أو authenticated) - التطبيق يحتاج فقط القراءة
drop policy if exists "updates_public_read" on public.updates;
create policy "updates_public_read"
  on public.updates
  for select
  to anon, authenticated
  using (true);

-- سياسة الكتابة (إدراج/تعديل/حذف): service_role فقط
-- (service_role يتجاوز RLS تلقائياً في Supabase، لكن نوضح القصد صراحة بمنع anon/authenticated)
drop policy if exists "updates_no_public_write" on public.updates;
create policy "updates_no_public_write"
  on public.updates
  for all
  to anon, authenticated
  using (false)
  with check (false);

-- ملاحظة: لا تضع مفتاح service_role في التطبيق أو الـ ISO أو Git أبداً.
-- استخدم فقط SUPABASE_URL و anon key داخل /etc/novaos/config.json،
-- والـ service_role key يُستخدم فقط من بيئة CI/CD (GitHub Actions secrets)
-- عند إضافة إصدار جديد لجدول updates.

-- نوع التحديث: fix (إصلاح) | feature (إضافة) | security (أمان)
alter table public.updates add column if not exists kind text not null default 'feature';
