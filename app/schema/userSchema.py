from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, func, Integer, Numeric
from sqlalchemy.orm import declarative_base, relationship

# 
Base = declarative_base()

# User Schema
class Users(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)                           # id Column String, PRIMARY KEY
    email = Column(String, unique=True, index=True)                             # email unique
    firstname = Column(String)                                                  # firstname
    lastname = Column(String)                                                   # lastname
    password = Column(String, nullable=False)                                   # password NOT NULL
    phone = Column(String)                                                      # phone
    role = Column(String, default="user")                                       # role DEFAULT 'user'
    companyid = Column(String, ForeignKey("companies.id"))                      # references companies.id
    isactive = Column(Boolean, default=True)                                    # isactive DEFAULT true
    lastlogin = Column(DateTime)                                                # lastlogin
    createdat = Column(DateTime, default=func.now())                            # createdat DEFAULT now()
    updatedat = Column(DateTime, default=func.now(), onupdate=func.now())       # updatedat DEFAULT now()

    # Relationship to companies table (optional)
    company = relationship("Company", back_populates="users")

# Companies Schema
class Companies(Base):
    __tablename__ = "companies"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True)
    phone = Column(String)
    address = Column(String)
    city = Column(String)
    state = Column(String)
    zipCode = Column(String)
    dotNumber = Column(String)
    mcNumber = Column(String)
    ein = Column(String)
    businessType = Column(String)
    yearsInBusiness = Column(Integer)
    numberOfTrucks = Column(Integer)
    walletBalance = Column(Numeric, default=0)
    subscriptionStatus = Column(String, default="trial")
    subscriptionPlan = Column(String, default="starter")
    stripeCustomerId = Column(String)
    railsrEnduserId = Column(String)
    railsrLedgerId = Column(String)
    bankAccountNumber = Column(String)
    bankRoutingNumber = Column(String)
    gustoCompanyId = Column(String)
    gustoAccessToken = Column(String)
    gustoRefreshToken = Column(String)
    gustoTokenExpiry = Column(DateTime)
    createdAt = Column(DateTime, default=func.now())
    updatedAt = Column(DateTime, default=func.now(), onupdate=func.now())
    isActive = Column(Boolean, default=True)
    handlesContainers = Column(Boolean, default=False)
    containerTrackingEnabled = Column(Boolean, default=False)

# Drivers Schema
# class Drivers(Base):
#     __tablename__ = "drivers"
# 
#     id = Column(String, primary_key=True, index=True)

# // Drivers - Matches actual database structure exactly
  export const drivers = pgTable("drivers", {   id: varchar("id").primaryKey().notNull(),
   companyId: varchar("companyid").references(() => companies.id).notNull(),
   firstName: varchar("firstname").notNull(),
   lastName: varchar("lastname").notNull(),
   email: varchar("email").notNull(),
   phone: varchar("phone").notNull(),
   licenseNumber: varchar("licensenumber").notNull(),
   licenseClass: varchar("licenseclass").notNull(),
   licenseExpiry: timestamp("licenseexpiry").notNull(),
   dateOfBirth: timestamp("dateofbirth").notNull(),
   address: varchar("address").notNull(),
   city: varchar("city").notNull(),
   state: varchar("state").notNull(),
   zipCode: varchar("zipcode").notNull(),
   emergencyContact: varchar("emergencycontact").notNull(),
   emergencyPhone: varchar("emergencyphone").notNull(),
   hireDate: timestamp("hiredate").notNull(),
   passwordHash: varchar("passwordhash").notNull(),
   status: varchar("status").default("available"),
   payRate: decimal("payrate").notNull(),
   payType: varchar("paytype").notNull(),
   hoursRemaining: decimal("hoursremaining"),
   currentLocation: varchar("currentlocation"),
   isActive: boolean("isactive").default(true),
   createdAt: timestamp("createdat").defaultNow(),
   updatedAt: timestamp("updatedat").defaultNow(),
 });