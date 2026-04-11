      * PAYROLL.CBL  -  Weekly Payroll Calculator
      *
      * Reads employee records from a flat file (EMPLOYEE-FILE),
      * computes gross pay, tax deductions and net pay for each
      * employee, accumulates company-wide totals, and writes a
      * summary report to REPORT-FILE.
      *
      * Business rules:
      *   - Regular hours  : first 40 h at base hourly rate
      *   - Overtime hours : hours beyond 40 at 1.5x base rate
      *   - Tax bracket 1  : gross <= $500   -> 10% tax
      *   - Tax bracket 2  : gross $501-$1500 -> 20% tax
      *   - Tax bracket 3  : gross > $1500    -> 30% tax
       IDENTIFICATION DIVISION.
       PROGRAM-ID.  PAYROLL.
       AUTHOR.      MY-DEV-TEAM-DEMO.


       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT EMPLOYEE-FILE ASSIGN TO 'employees.dat'
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT REPORT-FILE   ASSIGN TO 'payroll_report.txt'
               ORGANIZATION IS LINE SEQUENTIAL.


       DATA DIVISION.
       FILE SECTION.

       FD  EMPLOYEE-FILE.
       01  EMPLOYEE-RECORD.
           05  EMP-ID          PIC 9(5).
           05  EMP-NAME        PIC X(30).
           05  EMP-HOURS       PIC 9(3)V9.
           05  EMP-HOURLY-RATE PIC 9(4)V99.

       FD  REPORT-FILE.
       01  REPORT-LINE         PIC X(80).

       WORKING-STORAGE SECTION.

       01  WS-FLAGS.
           05  WS-EOF          PIC X VALUE 'N'.
               88  END-OF-FILE VALUE 'Y'.

       01  WS-PAY-CALCULATIONS.
           05  WS-REGULAR-HOURS  PIC 9(3)V9    VALUE ZEROS.
           05  WS-OVERTIME-HOURS PIC 9(3)V9    VALUE ZEROS.
           05  WS-REGULAR-PAY    PIC 9(6)V99   VALUE ZEROS.
           05  WS-OVERTIME-PAY   PIC 9(6)V99   VALUE ZEROS.
           05  WS-GROSS-PAY      PIC 9(6)V99   VALUE ZEROS.
           05  WS-TAX-AMOUNT     PIC 9(6)V99   VALUE ZEROS.
           05  WS-NET-PAY        PIC 9(6)V99   VALUE ZEROS.

       01  WS-COMPANY-TOTALS.
           05  WS-TOTAL-GROSS    PIC 9(9)V99   VALUE ZEROS.
           05  WS-TOTAL-TAX      PIC 9(9)V99   VALUE ZEROS.
           05  WS-TOTAL-NET      PIC 9(9)V99   VALUE ZEROS.
           05  WS-EMPLOYEE-COUNT PIC 9(5)      VALUE ZEROS.

       01  WS-REPORT-FIELDS.
           05  WS-DETAIL-LINE.
               10  FILLER           PIC X(5)  VALUE SPACES.
               10  WS-RPT-EMP-ID    PIC 9(5).
               10  FILLER           PIC X(2)  VALUE SPACES.
               10  WS-RPT-NAME      PIC X(30).
               10  FILLER           PIC X(2)  VALUE SPACES.
               10  WS-RPT-GROSS     PIC $ZZ,ZZ9.99.
               10  FILLER           PIC X(2)  VALUE SPACES.
               10  WS-RPT-TAX       PIC $ZZ,ZZ9.99.
               10  FILLER           PIC X(2)  VALUE SPACES.
               10  WS-RPT-NET       PIC $ZZ,ZZ9.99.
           05  WS-SUMMARY-LINE.
               10  FILLER           PIC X(37) VALUE SPACES.
               10  WS-RPT-TOT-GROSS PIC $ZZZ,ZZ9.99.
               10  FILLER           PIC X(2)  VALUE SPACES.
               10  WS-RPT-TOT-TAX   PIC $ZZZ,ZZ9.99.
               10  FILLER           PIC X(2)  VALUE SPACES.
               10  WS-RPT-TOT-NET   PIC $ZZZ,ZZ9.99.


       PROCEDURE DIVISION.

       0000-MAIN.
           PERFORM 1000-OPEN-FILES
           PERFORM 2000-PRINT-HEADER
           PERFORM 3000-PROCESS-EMPLOYEES
               UNTIL END-OF-FILE
           PERFORM 4000-PRINT-SUMMARY
           PERFORM 5000-CLOSE-FILES
           STOP RUN.


       1000-OPEN-FILES.
           OPEN INPUT  EMPLOYEE-FILE
           OPEN OUTPUT REPORT-FILE
           READ EMPLOYEE-FILE
               AT END MOVE 'Y' TO WS-EOF
           END-READ.


       2000-PRINT-HEADER.
           MOVE SPACES TO REPORT-LINE
           WRITE REPORT-LINE AFTER ADVANCING PAGE
           MOVE '           WEEKLY PAYROLL REPORT'
               TO REPORT-LINE
           WRITE REPORT-LINE AFTER ADVANCING 1 LINE
           MOVE SPACES TO REPORT-LINE
           WRITE REPORT-LINE AFTER ADVANCING 1 LINE
           MOVE '   ID    NAME                           GROSS' &
                '        TAX          NET'
               TO REPORT-LINE
           WRITE REPORT-LINE AFTER ADVANCING 1 LINE
           MOVE ALL '-' TO REPORT-LINE
           WRITE REPORT-LINE AFTER ADVANCING 1 LINE.


       3000-PROCESS-EMPLOYEES.
           PERFORM 3100-CALCULATE-PAY
           PERFORM 3200-CALCULATE-TAX
           PERFORM 3300-ACCUMULATE-TOTALS
           PERFORM 3400-PRINT-DETAIL
           READ EMPLOYEE-FILE
               AT END MOVE 'Y' TO WS-EOF
           END-READ.


       3100-CALCULATE-PAY.
           IF EMP-HOURS > 40
               MOVE 40            TO WS-REGULAR-HOURS
               SUBTRACT 40 FROM EMP-HOURS
                   GIVING WS-OVERTIME-HOURS
           ELSE
               MOVE EMP-HOURS     TO WS-REGULAR-HOURS
               MOVE ZEROS         TO WS-OVERTIME-HOURS
           END-IF

           MULTIPLY WS-REGULAR-HOURS BY EMP-HOURLY-RATE
               GIVING WS-REGULAR-PAY ROUNDED

           MULTIPLY WS-OVERTIME-HOURS BY EMP-HOURLY-RATE
               GIVING WS-OVERTIME-PAY ROUNDED
           MULTIPLY 1.5 BY WS-OVERTIME-PAY ROUNDED

           ADD WS-REGULAR-PAY WS-OVERTIME-PAY
               GIVING WS-GROSS-PAY.


       3200-CALCULATE-TAX.
           EVALUATE TRUE
               WHEN WS-GROSS-PAY <= 500.00
                   MULTIPLY 0.10 BY WS-GROSS-PAY
                       GIVING WS-TAX-AMOUNT ROUNDED
               WHEN WS-GROSS-PAY <= 1500.00
                   MULTIPLY 0.20 BY WS-GROSS-PAY
                       GIVING WS-TAX-AMOUNT ROUNDED
               WHEN OTHER
                   MULTIPLY 0.30 BY WS-GROSS-PAY
                       GIVING WS-TAX-AMOUNT ROUNDED
           END-EVALUATE

           SUBTRACT WS-TAX-AMOUNT FROM WS-GROSS-PAY
               GIVING WS-NET-PAY.


       3300-ACCUMULATE-TOTALS.
           ADD WS-GROSS-PAY      TO WS-TOTAL-GROSS
           ADD WS-TAX-AMOUNT     TO WS-TOTAL-TAX
           ADD WS-NET-PAY        TO WS-TOTAL-NET
           ADD 1                 TO WS-EMPLOYEE-COUNT.


       3400-PRINT-DETAIL.
           MOVE EMP-ID          TO WS-RPT-EMP-ID
           MOVE EMP-NAME        TO WS-RPT-NAME
           MOVE WS-GROSS-PAY    TO WS-RPT-GROSS
           MOVE WS-TAX-AMOUNT   TO WS-RPT-TAX
           MOVE WS-NET-PAY      TO WS-RPT-NET
           MOVE WS-DETAIL-LINE  TO REPORT-LINE
           WRITE REPORT-LINE AFTER ADVANCING 1 LINE.


       4000-PRINT-SUMMARY.
           MOVE ALL '-' TO REPORT-LINE
           WRITE REPORT-LINE AFTER ADVANCING 1 LINE
           MOVE WS-TOTAL-GROSS  TO WS-RPT-TOT-GROSS
           MOVE WS-TOTAL-TAX    TO WS-RPT-TOT-TAX
           MOVE WS-TOTAL-NET    TO WS-RPT-TOT-NET
           MOVE WS-SUMMARY-LINE TO REPORT-LINE
           WRITE REPORT-LINE AFTER ADVANCING 1 LINE
           MOVE SPACES          TO REPORT-LINE
           WRITE REPORT-LINE AFTER ADVANCING 1 LINE
           STRING 'Total employees processed: '
                  WS-EMPLOYEE-COUNT
               DELIMITED SIZE INTO REPORT-LINE
           WRITE REPORT-LINE AFTER ADVANCING 1 LINE.


       5000-CLOSE-FILES.
           CLOSE EMPLOYEE-FILE
           CLOSE REPORT-FILE.
