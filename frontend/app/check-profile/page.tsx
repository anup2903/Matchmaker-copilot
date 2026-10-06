import { Suspense } from "react";
import { LoadingBlock } from "@/components/ui";
import { CheckProfileView } from "./check-profile-view";

export default function CheckProfilePage() {
  return (
    <Suspense fallback={<LoadingBlock />}>
      <CheckProfileView />
    </Suspense>
  );
}
