"use client";

import dynamic from "next/dynamic";
import { Skeleton } from "@/components/ui/states";

export const MapView = dynamic(
  () => import("./map-view").then((m) => m.MapView),
  {
    ssr: false,
    loading: () => <Skeleton className="h-full w-full" />,
  }
);
