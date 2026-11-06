"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQuery } from "@tanstack/react-query";
import { academicsApi, type Student } from "@/lib/api/academics";
import { useAppSession } from "@/lib/auth/use-app-session";

export type ParentChild = {
  id: string;
  name: string;
  className: string;
};

type ParentChildrenContextValue = {
  children: ParentChild[];
  selectedChildId: string | null;
  selectChild: (id: string) => void;
  selected: ParentChild | null;
  isLoading: boolean;
  error: Error | null;
};

const ParentChildrenContext = createContext<ParentChildrenContextValue | null>(
  null,
);

function studentLabel(s: Student): ParentChild {
  const name =
    s.full_name ||
    [s.first_name, s.last_name].filter(Boolean).join(" ") ||
    s.admission_number ||
    s.id;
  return {
    id: s.id,
    name,
    className: s.admission_number ?? "",
  };
}

export function ParentChildrenProvider({ children }: { children: ReactNode }) {
  const { role, accessToken, ready } = useAppSession();
  const enabled = ready && role === "parent" && Boolean(accessToken);
  const [selectedChildId, setSelectedChildId] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["academics", "my-students"],
    queryFn: () => academicsApi.myStudents(),
    enabled,
  });

  const list = useMemo(
    () => (query.data ?? []).map(studentLabel),
    [query.data],
  );

  useEffect(() => {
    if (!list.length) {
      setSelectedChildId(null);
      return;
    }
    if (!selectedChildId || !list.some((c) => c.id === selectedChildId)) {
      setSelectedChildId(list[0].id);
    }
  }, [list, selectedChildId]);

  const selectChild = useCallback((id: string) => {
    setSelectedChildId(id);
  }, []);

  const value = useMemo<ParentChildrenContextValue>(
    () => ({
      children: list,
      selectedChildId,
      selectChild,
      selected: list.find((c) => c.id === selectedChildId) ?? null,
      isLoading: query.isLoading,
      error: query.error,
    }),
    [list, selectedChildId, selectChild, query.isLoading, query.error],
  );

  return (
    <ParentChildrenContext.Provider value={value}>
      {children}
    </ParentChildrenContext.Provider>
  );
}

export function useParentChildren() {
  const ctx = useContext(ParentChildrenContext);
  if (!ctx) {
    throw new Error("useParentChildren must be used within ParentChildrenProvider");
  }
  return ctx;
}
