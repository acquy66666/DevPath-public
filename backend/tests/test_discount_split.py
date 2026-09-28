"""Splitting one order's discount across the lines it was taken off.

An order stores one discount, but a course has one instructor, and the
instructor's revenue dashboard has to know how much of that discount fell on
*their* course. Reading it back later from the coupon's scope is not an answer:
the scope can be edited after the sale. So the split is done once, when the
order is written, and frozen onto `order_items.discount`.

Two properties matter and both are pinned here with numbers worked out by hand:
the shares add up to the discount to the đồng, and no line is discounted by
more than it cost.
"""

from decimal import Decimal

from app.services.coupons import split_discount


def dong(*values: int) -> list[Decimal]:
    return [Decimal(value) for value in values]


def test_the_shares_follow_the_prices() -> None:
    # 50% of 998.000: 399.000 → 199.500, 599.000 → 299.500. Exact, no rounding.
    assert split_discount(Decimal("499000"), dong(399000, 599000)) == dong(199500, 299500)


def test_the_shares_add_up_to_the_discount_to_the_dong() -> None:
    # 100.000 over three equal lines is 33.333,33 each. Rounding each down
    # loses one đồng; it goes to the first line, not nowhere.
    shares = split_discount(Decimal("100000"), dong(199000, 199000, 199000))

    assert shares == dong(33334, 33333, 33333)
    assert sum(shares) == Decimal("100000")


def test_the_leftover_dong_goes_to_the_largest_remainder() -> None:
    # 10 over 10 + 20: exact shares 3,33 and 6,67. Floors are 3 and 6; the
    # đồng left over belongs to the line that was rounded down the most.
    assert split_discount(Decimal("10"), dong(10, 20)) == dong(3, 7)


def test_no_line_is_discounted_by_more_than_it_cost() -> None:
    # A voucher that swallows the whole cart takes each line to exactly zero.
    prices = dong(199000, 300000, 1)

    assert split_discount(Decimal("499001"), prices) == prices


def test_no_discount_is_no_discount_on_any_line() -> None:
    assert split_discount(Decimal("0"), dong(199000, 300000)) == dong(0, 0)


def test_free_lines_share_nothing_and_divide_by_nothing() -> None:
    # A cart of free courses takes a code for nothing off. The split must not
    # turn that into a division by a zero subtotal.
    assert split_discount(Decimal("0"), dong(0, 0)) == dong(0, 0)


def test_a_free_line_next_to_a_paid_one_takes_none_of_the_discount() -> None:
    assert split_discount(Decimal("50000"), dong(0, 100000)) == dong(0, 50000)
