import { Placeholder } from "@/components/placeholder";

export default async function Page({ params }: PageProps<"/[locale]/kyc/[orderId]">) {
  const { orderId } = await params;
  return <Placeholder titleKey="kycTitle" orderId={orderId} />;
}
