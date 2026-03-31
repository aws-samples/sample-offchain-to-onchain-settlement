export const truncateAddress = (addr: string) => (addr ? `${addr.slice(0, 6)}...${addr.slice(-4)}` : '');

export const formatAmount = (wei: string, decimals = 18) => {
  const base = BigInt(10) ** BigInt(decimals);
  const amount = BigInt(wei);
  const num = amount / base;
  const remainder = amount % base;
  return remainder > 0n ? `${num}.${remainder.toString().padStart(decimals, '0').slice(0, 4)}` : num.toString();
};
