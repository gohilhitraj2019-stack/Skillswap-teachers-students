from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_
from app.student import student_bp
from app.extensions import db
from app.models.user import User
from app.models.teacher import TeacherProfile, Availability
from app.models.skill import Skill, SkillCategory, TeacherSkill
from app.models.booking import Booking
from app.models.review import Review
from app.models.notification import Notification
from app.services.credit_service import ensure_wallet
from app.services.notification_service import create_notification

@student_bp.route('/student/dashboard')
@login_required
def dashboard():
    wallet = ensure_wallet(current_user.id)

    # Upcoming bookings (confirmed or pending)
    upcoming_bookings = Booking.query.filter(
        Booking.student_id == current_user.id,
        Booking.status.in_(['pending', 'confirmed'])
    ).order_by(Booking.class_date.asc(), Booking.start_time.asc()).limit(5).all()

    # Completed bookings
    completed_bookings = Booking.query.filter(
        Booking.student_id == current_user.id,
        Booking.status == 'completed'
    ).order_by(Booking.completed_at.desc()).limit(5).all()

    # Recent transactions
    recent_transactions = wallet.transactions[:6] if wallet.transactions else []

    # Recommended teachers (approved, top rated)
    recommended_teachers = TeacherProfile.query.filter_by(approval_status='approved')\
        .order_by(TeacherProfile.avg_rating.desc(), TeacherProfile.total_classes.desc())\
        .limit(4).all()

    return render_template(
        'student/dashboard.html',
        wallet=wallet,
        upcoming_bookings=upcoming_bookings,
        completed_bookings=completed_bookings,
        recent_transactions=recent_transactions,
        recommended_teachers=recommended_teachers
    )


@student_bp.route('/explore')
def explore():
    category_slug = request.args.get('category', '').strip()
    skill_query = request.args.get('q', '').strip()
    min_price = request.args.get('min_price', type=int)
    max_price = request.args.get('max_price', type=int)
    min_rating = request.args.get('min_rating', type=float)
    min_exp = request.args.get('min_exp', type=int)
    language = request.args.get('language', '').strip()

    # Only approved teachers
    query = TeacherProfile.query.filter_by(approval_status='approved')

    # Join User to search teacher names or filter active users
    query = query.join(User, TeacherProfile.user_id == User.id).filter(User.is_active.is_(True))

    if category_slug:
        cat = SkillCategory.query.filter_by(slug=category_slug).first()
        if cat:
            query = query.join(TeacherSkill, TeacherSkill.teacher_profile_id == TeacherProfile.id)\
                         .join(Skill, TeacherSkill.skill_id == Skill.id)\
                         .filter(Skill.category_id == cat.id)

    if skill_query:
        query = query.outerjoin(TeacherSkill, TeacherSkill.teacher_profile_id == TeacherProfile.id)\
                     .outerjoin(Skill, TeacherSkill.skill_id == Skill.id)\
                     .filter(or_(
                         User.name.ilike(f'%{skill_query}%'),
                         TeacherProfile.title.ilike(f'%{skill_query}%'),
                         TeacherProfile.bio.ilike(f'%{skill_query}%'),
                         Skill.name.ilike(f'%{skill_query}%')
                     )).distinct()

    if min_price is not None:
        query = query.filter(TeacherProfile.hourly_rate >= min_price)
    if max_price is not None:
        query = query.filter(TeacherProfile.hourly_rate <= max_price)
    if min_rating is not None:
        query = query.filter(TeacherProfile.avg_rating >= min_rating)
    if min_exp is not None:
        query = query.filter(TeacherProfile.experience_years >= min_exp)
    if language:
        query = query.filter(TeacherProfile.languages.ilike(f'%{language}%'))

    teachers = query.order_by(TeacherProfile.avg_rating.desc(), TeacherProfile.total_classes.desc()).all()
    categories = SkillCategory.query.order_by(SkillCategory.name).all()

    return render_template(
        'student/explore.html',
        teachers=teachers,
        categories=categories,
        current_category=category_slug,
        current_query=skill_query,
        min_price=min_price,
        max_price=max_price,
        min_rating=min_rating,
        min_exp=min_exp,
        language=language
    )


@student_bp.route('/teacher/<int:teacher_id>')
def teacher_profile(teacher_id):
    profile = TeacherProfile.query.filter_by(user_id=teacher_id).first_or_404()
    if not profile.is_approved and (not current_user.is_authenticated or (not current_user.is_admin and current_user.id != teacher_id)):
        flash('This teacher profile is pending verification.', 'warning')
        return redirect(url_for('student.explore'))

    reviews = Review.query.filter_by(teacher_id=teacher_id).order_by(Review.created_at.desc()).all()
    availabilities = Availability.query.filter_by(teacher_profile_id=profile.id, is_active=True).order_by(Availability.day_of_week).all()

    return render_template(
        'student/teacher_profile.html',
        profile=profile,
        reviews=reviews,
        availabilities=availabilities
    )


@student_bp.route('/student/bookings')
@login_required
def bookings():
    status_filter = request.args.get('status', 'all')
    query = Booking.query.filter_by(student_id=current_user.id)

    if status_filter == 'upcoming':
        query = query.filter(Booking.status.in_(['pending', 'confirmed']))
    elif status_filter == 'completed':
        query = query.filter_by(status='completed')
    elif status_filter == 'cancelled':
        query = query.filter(Booking.status.in_(['cancelled_by_student', 'cancelled_by_teacher', 'rejected']))

    user_bookings = query.order_by(Booking.class_date.desc(), Booking.start_time.desc()).all()
    return render_template('student/bookings.html', bookings=user_bookings, current_status=status_filter)


@student_bp.route('/student/review/<int:booking_id>', methods=['POST'])
@login_required
def submit_review(booking_id):
    booking = Booking.query.get_or_404(booking_id)

    if booking.student_id != current_user.id:
        flash('Unauthorized.', 'danger')
        return redirect(url_for('student.bookings'))

    if booking.status != 'completed':
        flash('You can only review completed classes.', 'warning')
        return redirect(url_for('student.bookings'))

    if booking.review:
        flash('You have already submitted a review for this class.', 'info')
        return redirect(url_for('student.bookings'))

    rating = request.form.get('rating', type=int)
    comment = request.form.get('comment', '').strip()

    if not rating or rating < 1 or rating > 5:
        flash('Please provide a valid rating between 1 and 5 stars.', 'danger')
        return redirect(url_for('student.bookings'))

    review = Review(
        booking_id=booking.id,
        student_id=current_user.id,
        teacher_id=booking.teacher_id,
        rating=rating,
        comment=comment
    )
    db.session.add(review)
    db.session.flush()

    # Recalculate teacher avg rating
    if booking.teacher_profile:
        booking.teacher_profile.recalculate_rating()

    create_notification(
        booking.teacher_id,
        title="New Class Review Received",
        message=f"{current_user.name} rated your class {rating} stars: \"{comment[:80]}...\"",
        link=f"/teacher/{booking.teacher_id}"
    )

    db.session.commit()
    flash('Thank you! Your review has been submitted.', 'success')
    return redirect(url_for('student.bookings'))


@student_bp.route('/notifications')
@login_required
def notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    # Mark all read
    for n in notifs:
        n.is_read = True
    db.session.commit()
    return render_template('student/notifications.html', notifications=notifs)
