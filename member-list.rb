class MemberList

	def initialize
		@members = Hash.new()
	end

	def getMember(name)
		if !@members.has_key?(name)
			@members[name] = Member.new(name)
		end

		@members[name]
	end

	def list
		@members.values
	end
end

class Member

	def initialize(name)
		@name = name
	end

	# Name of the member
	def name
		@name
	end

	def name=(name)
		@name = name
	end

	# Website of the member
	def website
		@website
	end

	def website=(website)
		@website = website
	end

	# Email of the member
	def email
		@email
	end

	def email=(email)
		@email = email
	end

	# If the member has contributed to the website
	def contributed
		if @contributed.nil? then false else @contributed end
	end

	def contributed=(contributed)
		@contributed = contributed
	end

	# The talks that the member did
	def talks
		if !defined?(@talk) or @talk == nil
			@talk = []
		end

		@talk
	end

	# Badges
	def badges
		lstBadges = []

		if @talk.length >= 1
			lstBadges.push({ :color => "bronze", :value => "Speaker" })
		end

		if @talk.length >= 5
			lstBadges.push({ :color => "silver", :value => "Orator" })
		end

		if @talk.length >= 15
			lstBadges.push({ :color => "gold", :value => "Speechmaker" })
		end

		if contributed
			lstBadges.push({ :color => "bronze", :value => "Website builder" })
		end

		lstBadges
	end
end