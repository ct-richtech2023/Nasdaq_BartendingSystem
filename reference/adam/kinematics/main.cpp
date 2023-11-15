#include "xarm_kinematics_interface.h"
#include <stdlib.h>
#include <stdio.h>
#include <math.h>
/* Test xArm6 FK and IK at the same time */
/* input: joint angles (dimension: DOF) in degree */

/* *************************************************/
/* execution example: ./main 10 -30 -25 100 0 -52  */
/* *************************************************/

int main(int argc, char **argv)
{
	double deg2rad = M_PI/180.0; // convert from degree to radian

	if(argc!=25){
	    fprintf(stderr, "argc not == 19(1+6+6+6+6)\n" );
		exit(-1);
	}

	double theta[6]={0}, theta_sol[6]={0}, tcp_offset[6]={0}, world_offset[6]={0}, q_pre[6]={0};

	for(int j=0;j<6;j++)
		theta[j] = std::atof(argv[j+1])*deg2rad;

	for(int j=0;j<6;j++)
		if (j<3) tcp_offset[j] = std::atof(argv[j+7]);
		else tcp_offset[j] = std::atof(argv[j+7])*deg2rad;

	for(int j=0;j<6;j++)
		if (j<3) world_offset[j] = std::atof(argv[j+13]);
		else world_offset[j] = std::atof(argv[j+13])*deg2rad;

	for(int j=0;j<6;j++)
		q_pre[j] = std::atof(argv[j+19])*deg2rad;

	/* For xArm6 or 7, joint limits have to be passed, just use the Macros defined in 'xarm_kinematics_interface.h' */
	double q_min[6] = XARM6_ANGLE_MIN; // Use LIMITED joint range, strange solution may be avoided
	double q_max[6] = XARM6_ANGLE_MAX;

	/* q_pre: starting joint angle, reference joint angle */
	// double q_pre[6] = {0, 0, 0, 0, 0, 0};

	double T[4][4] = {0}, pose_rpy[6] = {0};
	//double tcp_offset[6] = {0,0,0, 0,0,0}; // change if there is any TCP offset, unit: mm, rad

	// * Attention! MUST BE Configured before calling FK or IK !
	xarm6_config(q_max, q_min, tcp_offset, world_offset);


	/*** Method 1: Use Transformation Matrix as TCP expression */
	int ret = xarm6_forward_kinematics(theta, T); // result is in transformation matrix

	fprintf(stderr, "xarm6 FK (Matrix) result:\n" );
	for(int i=0; i<4; i++)
	{
		for(int j=0; j<4; j++)
			fprintf(stderr, "%lf,\t", T[i][j]);
		fprintf(stderr, "\n");
	}

	/* T: target Transformation matrix, theta_sol: solution angles */
	/* For xarm6 or 7, just return the first solution found iteratively */
	/* For xArm5, return the solution closest to q_pre. */
	ret = xarm6_inverse_kinematics(T, q_pre, theta_sol);

	if(ret)
	{
		fprintf(stderr, "\nIK (Matrix) returns: %d, Solution Fail!\n", ret);
	}
	else
	{
		fprintf(stderr, "\nIK (Matrix) returns: %d, solution:\t", ret);
		for(int i=0; i<6; i++)
			fprintf(stderr, "%lf,\t", theta_sol[i]/deg2rad);
		fprintf(stderr, "\n" );
	}


	/*** Method 2: Use [x,y,z,roll,pitch,yaw] as TCP expression */
	ret = xarm6_forward_kinematics(theta, pose_rpy);
	fprintf(stderr, "\nxarm6 FK (Pose) result:\n" );
	for(int i=0; i<3; i++)
	{
		fprintf(stderr, "%lf,\t", pose_rpy[i]);
	}
	for(int i=0; i<3; i++)
	{
		fprintf(stderr, "%lf,\t", pose_rpy[i+3]*180.0/M_PI);
	}

	fprintf(stderr, "\n");

	ret = xarm6_inverse_kinematics(pose_rpy, q_pre, theta_sol);

	if(ret)
	{
		fprintf(stderr, "\nIK (Pose) returns: %d, Solution Fail!\n", ret);
		exit(-1);
	}
	else
	{
		fprintf(stderr, "\nIK (Pose) returns: %d, solution:\t", ret);
		for(int i=0; i<6; i++)
			fprintf(stderr, "%lf,\t", theta_sol[i])/deg2rad;
		fprintf(stderr, "\n" );
	}

	return 0;
}
