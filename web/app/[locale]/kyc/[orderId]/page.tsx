import { KycFlow } from "@/components/kyc-flow";

export default async function Page({ params }: PageProps<"/[locale]/kyc/[orderId]">) {
  const { orderId } = await params;
  return <KycFlow orderId={orderId} />;
}
