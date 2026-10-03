import { redirect } from "next/navigation";

export default function InvestigateIndexPage() {
  // Default to the primary model detection dataset
  redirect("/investigate/IN-250825-001");
}
