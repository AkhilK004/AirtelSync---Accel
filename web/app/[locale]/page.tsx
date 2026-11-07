import { Suspense } from "react";
import { Landing } from "@/components/landing";

export default function Page() {
  return (
    <Suspense>
      <Landing />
    </Suspense>
  );
}
