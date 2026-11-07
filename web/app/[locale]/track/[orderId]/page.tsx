import { Suspense } from "react";
import { OrderTracker } from "@/components/order-tracker";

export default async function Page({ params }: PageProps<"/[locale]/track/[orderId]">) {
  const { orderId } = await params;
  return (
    <Suspense>
      <OrderTracker orderId={orderId} />
    </Suspense>
  );
}
