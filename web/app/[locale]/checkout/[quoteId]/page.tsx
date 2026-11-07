import { CheckoutForm } from "@/components/checkout-form";

export default async function Page({ params }: PageProps<"/[locale]/checkout/[quoteId]">) {
  const { quoteId } = await params;
  return <CheckoutForm quoteId={quoteId} />;
}
