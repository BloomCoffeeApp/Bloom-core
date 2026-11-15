/** A birthday without a year is stored with this placeholder year (a leap year, so 29/02 is valid).
 * The backend only compares month and day for the birthday alert; the age is hidden for this year. */
export const NO_YEAR = 1904

export const hasBirthYear = (birthday: string) => Number(birthday.slice(0, 4)) !== NO_YEAR
