
def calcLiquidity(c, r):
	n = c/(2*(1-r))
	y = c/(2*r)
	ls = 0
	if (n > c):
		# yes more likely
		y = c/n*y
		n = c
		ls = n*(1-r)*2
		# residual cash
		r_c = c-ls
		r_y = r_c / r
		r_n = 0
	else:
		# no more likely
		n = c/y*n
		y = c
		ls = y*r*2
		r_c = c-ls
		r_y = 0
		r_n = r_c / (1-r)
	return (y, n, r_y, r_n, ls)

LIQ_FEE = 0.0

# due to the constant product rule, LPs are short convexity somewhat
class CPMM(object):

	def __init__(self):
		# initialize
		self.noShares = 0
		self.yesShares = 0
		# excess shares of liquidity pool
		self.noResidShares = 0
		self.yesResidShares = 0
		self.lps = {}
		self.trades = {}
		self.liqFees = {}
		self.stable = 0

	def distLiqFee(self, liqFee):
		totLiqShares = sum(self.lps.values())
		for lp in self.lps:
			if lp in self.liqFees:
				self.liqFees[lp] += self.lps[lp] / totLiqShares * liqFee
			else:
				self.liqFees[lp] = self.lps[lp] / totLiqShares * liqFee

	def getRate(self):
		return self.noShares / (self.noShares + self.yesShares)

	def getLiqFees(self):
		return self.liqFees

	def getLiqUsersValueWithFees(self):
		return self.getLiqUsersValue()+self.getLiqFeesValue()

	def getLiqUsersValue(self):
		return (self.getLiqPoolValue()+self.getLiqResidValue())

	def getLiqPoolValue(self):
		r = self.getRate()
		return self.yesShares*r+self.noShares*(1-r)

	def getLiqResidValue(self):
		r = self.getRate()
		return self.yesResidShares*r+self.noResidShares*(1-r)

	def getLiqFeesValue(self):
		return sum(self.liqFees.values())

	def getYesPotentialWin(self):
		return sum([self.trades[x]['yes'] for x in self.trades])

	def getNoPotentialWin(self):
		return sum([self.trades[x]['no'] for x in self.trades])

	'''def addTrade(self, addr, typ_, dir_, n, px):
		if addr in self.trades:
			self.trades[addr].append(Trade(typ_, dir_, n, px))
		else:
			self.trades[addr] = [Trade(typ_, dir_, n, px)]'''

	def addTrade(self, addr, typ_, dir_, n):
		if addr in self.trades:
			if typ_:
				self.trades[addr]['yes'] += (dir_*n)
			else:
				self.trades[addr]['no'] += (dir_*n)
		else:
			self.trades[addr] = {}
			if typ_:
				self.trades[addr]['yes'] = (dir_*n)
				self.trades[addr]['no'] = 0
			else:
				self.trades[addr]['yes'] = 0
				self.trades[addr]['no'] = (dir_*n)

	def addLiquidity(self, addr, c, r=None):
		# no liquidity has been added yet
		if (self.noShares == 0) or (self.yesShares == 0):
			y, n, r_y, r_n, ls = calcLiquidity(c, r)
		else:
			y, n, r_y, r_n, ls = calcLiquidity(c, self.getRate())
		self.lps[addr] = ls
		self.noShares += n
		self.yesShares += y

		if r_y:
			self.addTrade(addr, True, 1, r_y)
			self.yesResidShares += r_y
		elif r_n:
			self.addTrade(addr, False, 1, r_n)
			self.noResidShares += r_n

		self.stable += c

	def removeLiquidity(self, addr, nShares):
		# need enough liq shares
		assert(self.lps[addr] >= nShares)

		# create market positions from shares
		totLiqShares = sum(self.lps.values())
		px = self.getRate()
		yesShares = self.yesShares * nShares / totLiqShares
		noShares = self.noShares * nShares / totLiqShares

		self.addTrade(addr, True, 1, yesShares)
		self.addTrade(addr, False, 1, noShares)

		self.yesShares -= yesShares
		self.noShares -= noShares
		self.liqFees[addr] -= nShares / self.lps[addr] * self.liqFees[addr]
		self.lps[addr] -= nShares

		# remove from amm
		if self.lps[addr] == 0:
			del self.lps[addr]
			del self.liqFees[addr]

	def mergeShares(self, addr, pct):
		# pct is amt of mergeable set to merge for stablecoins
		yesShares = self.trades[addr]['yes']
		noShares = self.trades[addr]['no']
		assert((yesShares > 0) and (noShares > 0))

		globalRatio = self.yesShares / self.noShares
		userRatio = yesShares / noShares
		rate = self.getRate()
		if globalRatio > userRatio:
			# then users' yes shares are limiting factor
			mergeYesShares = pct * yesShares
			mergeNoShares = 1./globalRatio * mergeYesShares
		else:
			# then users' no shares are limiting factor
			mergeNoShares = pct * noShares
			mergeYesShares = globalRatio * mergeNoShares

		mktValue = mergeYesShares*rate+mergeNoShares*(1-rate)
		self.trades[addr]['yes'] -= mergeYesShares
		self.trades[addr]['no'] -= mergeNoShares
		if ((self.trades[addr]['yes'] < 0.00000001) and (self.trades[addr]['no'] < 0.00000001)):
			del self.trades[addr]
		self.stable -= mktValue

	'''def printTrades(self):
		for addr in self.trades:
			for trade in self.trades[addr]:
				print(trade)'''

	def buyShares(self, addr, typ_, c):

		liqFee = LIQ_FEE * c
		c -= liqFee
		self.distLiqFee(liqFee)

		noShares = self.noShares
		yesShares = self.yesShares
		prod = noShares*yesShares
		if typ_:
			d = yesShares+c-prod/(noShares+c)
			yesShares += (c-d)
			noShares += c
		else:
			d = noShares+c-prod/(yesShares+c)
			yesShares += c
			noShares += (c-d)
		self.yesShares = yesShares
		self.noShares = noShares
		px = c / d
		print("Price:",px)
		self.addTrade(addr, typ_, 1, d)
		self.stable += c

def main():
	m = CPMM()
	print("Add $100 liquidity with 50% seed:")
	m.addLiquidity("a", 100, 0.5)
	print("LPs:", m.lps)
	print("No Shares: %f" % (m.noShares))
	print("Yes Shares: %f" % (m.yesShares))
	print("Current stablecoin count", m.stable)
	print("Add $1 liquidity:")
	m.addLiquidity("b", 1)
	print("LPs:", m.lps)
	print("No Shares: %f" % (m.noShares))
	print("Yes Shares: %f" % (m.yesShares))
	print("Current stablecoin count", m.stable)
	print("Current trades", m.trades)
	print("c buys $150 yes shares: ")
	m.buyShares("c", True, 150)
	print("Trades:", m.trades)
	print("Current stablecoin count", m.stable)
	print("No Shares: %f" % (m.noShares))
	print("Yes Shares: %f" % (m.yesShares))
	print("Redeem $100 liquidity from a")
	m.removeLiquidity("a",100.)
	print("LPs:", m.lps)
	print("No Shares: %f" % (m.noShares))
	print("Yes Shares: %f" % (m.yesShares))
	print("Current stablecoin count", m.stable)
	print("Merge trades from a")
	m.mergeShares("a",1.)
	print("Trades:", m.trades)
	print("Current stablecoin count", m.stable)
	print("Possible yes winnings,", m.getYesPotentialWin())
	print("Possible yes winnings,", m.getNoPotentialWin())


if __name__ == '__main__':
	main()

