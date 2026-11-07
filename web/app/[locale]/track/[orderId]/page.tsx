import { Placeholder } from "@/components/placeholder";

export default async function Page({ params }: PageProps<"/[locale]/track/[orderId]">) {
  const { orderId } = await params;
  return <Placeholder titleKey="trackTitle" orderId={orderId} />;
}
