import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://qmjwnfmcdepibytbirbl.supabase.co';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFtanduZm1jZGVwaWJ5dGJpcmJsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTA4NDE5NTEsImV4cCI6MjEwNjQxNzk1MX0.DnM5kzWjwbXGuTlvbgO8Ert4HkqPJwC4sogZxIquI-Q';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
