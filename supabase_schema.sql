-- Create table for storing groupings
-- Run this in your Supabase SQL Editor

CREATE TABLE groupings (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  filename TEXT NOT NULL,
  number_of_groups INTEGER NOT NULL,
  columns TEXT[] NOT NULL,
  groups JSONB NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for faster queries
CREATE INDEX idx_groupings_created_at ON groupings(created_at DESC);

-- Enable Row Level Security (optional - allows anyone to read/write for now)
ALTER TABLE groupings ENABLE ROW LEVEL SECURITY;

-- Policy: Allow anyone to insert
CREATE POLICY "Allow public insert" ON groupings
  FOR INSERT TO anon
  WITH CHECK (true);

-- Policy: Allow anyone to select
CREATE POLICY "Allow public select" ON groupings
  FOR SELECT TO anon
  USING (true);

-- Policy: Allow anyone to delete
CREATE POLICY "Allow public delete" ON groupings
  FOR DELETE TO anon
  USING (true);
